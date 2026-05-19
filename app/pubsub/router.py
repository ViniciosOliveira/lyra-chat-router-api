import base64
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy import text

from app.audit.logger import AuditLogger
from app.core.config import Settings, get_settings
from app.db.session import get_engine
from app.googlechat.schemas import NormalizedChatEvent
from app.handlers.openclaw_agent_hook import OpenClawAgentHookError, enqueue_openclaw_agent_turn
from app.policies.engine import PolicyEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/googlechat/events", tags=["googlechat-events"])


def _decode_pubsub_payload(payload: dict[str, Any]) -> dict[str, Any]:
    message = payload.get("message") or {}
    data = message.get("data")
    if not isinstance(data, str) or not data:
        raise HTTPException(status_code=400, detail="Missing Pub/Sub message data")
    try:
        decoded = base64.b64decode(data).decode("utf-8")
        value = json.loads(decoded)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid Pub/Sub message data") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="Unexpected Pub/Sub data shape")
    return value


def _event_data(cloud_event: dict[str, Any]) -> dict[str, Any]:
    data = cloud_event.get("data")
    if isinstance(data, dict):
        return data
    return cloud_event


def _extract_message_resource(cloud_event: dict[str, Any]) -> dict[str, Any] | None:
    data = _event_data(cloud_event)
    message = data.get("message")
    if isinstance(message, dict):
        return message
    # Some batch events include items like {"messages": [{"message": {...}}]}.
    messages = data.get("messages")
    if isinstance(messages, list) and messages:
        first = messages[0]
        if isinstance(first, dict):
            nested = first.get("message")
            if isinstance(nested, dict):
                return nested
            if first.get("name"):
                return first
    return None


def normalize_workspace_event(cloud_event: dict[str, Any]) -> NormalizedChatEvent:
    message = _extract_message_resource(cloud_event)
    if not message:
        raise HTTPException(status_code=202, detail="No message resource in event")

    space = message.get("space") or {}
    sender = message.get("sender") or {}
    thread = message.get("thread") or {}
    event_type = str(cloud_event.get("type") or cloud_event.get("eventType") or "UNKNOWN")
    text_value = message.get("argumentText") or message.get("text") or ""

    return NormalizedChatEvent(
        event_type=event_type,
        space_name=space.get("name"),
        space_display_name=space.get("displayName"),
        user_name=sender.get("name"),
        user_display_name=sender.get("displayName"),
        user_email=sender.get("email"),
        thread_name=thread.get("name"),
        message_name=message.get("name"),
        text=str(text_value).strip(),
        raw=cloud_event,
    )


def _is_bot_message(event: NormalizedChatEvent, settings: Settings) -> bool:
    sender = (_extract_message_resource(event.raw) or {}).get("sender") or {}
    sender_type = str(sender.get("type") or "").upper()
    if sender_type in {"BOT", "APP"}:
        return True
    return bool(settings.google_chat_bot_user and event.user_name == settings.google_chat_bot_user)


def _is_duplicate_message(event: NormalizedChatEvent) -> bool:
    if not event.message_name:
        return False
    engine = get_engine()
    if engine is None:
        return False
    with engine.connect() as conn:
        count = conn.execute(
            text("select count(*) from messages where provider_message_id = :message_name"),
            {"message_name": event.message_name},
        ).scalar_one()
    return int(count) > 0


def _verify_pubsub_request(
    settings: Settings,
    authorization: str | None,
    x_router_secret: str | None,
    query_secret: str | None,
) -> None:
    # MVP protection for push delivery. Pub/Sub push doesn't support arbitrary custom
    # headers, so we accept either the manual-smoke header or a subscription endpoint
    # query secret. Replace with Pub/Sub OIDC validation after the Cloud subscription
    # service account is finalized.
    if settings.google_chat_pubsub_shared_secret:
        provided_secret = x_router_secret or query_secret
        if provided_secret != settings.google_chat_pubsub_shared_secret:
            raise HTTPException(status_code=401, detail="Invalid Pub/Sub router secret")
        return
    if settings.is_prod:
        # Fail closed in production unless a secret has been configured.
        raise HTTPException(status_code=503, detail="Pub/Sub endpoint is not configured")


@router.post("/pubsub")
async def receive_pubsub_event(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    x_lyra_router_secret: str | None = Header(default=None),
    secret: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _verify_pubsub_request(settings, authorization, x_lyra_router_secret, secret)
    payload = await request.json()
    cloud_event = _decode_pubsub_payload(payload)
    event = normalize_workspace_event(cloud_event)

    if _is_bot_message(event, settings):
        return {"status": "ignored", "reason": "bot_message"}
    if _is_duplicate_message(event):
        return {"status": "ignored", "reason": "duplicate_message"}

    decision = PolicyEngine().decide(event)
    if decision.decision != "allow":
        # Unknown/unauthorized spaces are acknowledged but not answered.
        AuditLogger().record_routing(
            event=event,
            decision=decision,
            response={"status": "ignored", "reason": decision.reason},
        )
        return {"status": "ignored", "reason": decision.reason}

    if not settings.openclaw_agent_hook_enabled:
        AuditLogger().record_routing(
            event=event,
            decision=decision,
            response={"status": "accepted", "handler": "pubsub_noop"},
        )
        return {"status": "accepted", "handler": "pubsub_noop"}

    try:
        hook_response = await enqueue_openclaw_agent_turn(
            settings=settings,
            event=event,
            decision=decision,
        )
    except OpenClawAgentHookError as exc:
        logger.exception("pubsub_openclaw_agent_hook_failed")
        AuditLogger().record_routing(
            event=event,
            decision=decision,
            response={"status": "error", "error": str(exc)},
        )
        # Return 500 so Pub/Sub can retry transient OpenClaw failures.
        raise HTTPException(status_code=500, detail="OpenClaw hook failed") from exc

    AuditLogger().record_routing(
        event=event,
        decision=decision,
        response={"status": "queued", "hook_response": hook_response},
    )
    response.status_code = 202
    return {"status": "queued"}
