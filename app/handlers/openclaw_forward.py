import logging
from copy import deepcopy
from typing import Any

import requests
from fastapi.concurrency import run_in_threadpool

from app.core.config import Settings
from app.googlechat.schemas import NormalizedChatEvent
from app.policies.engine import PolicyDecision

logger = logging.getLogger(__name__)


class OpenClawForwardError(RuntimeError):
    pass


def _strip_thread_delivery_context(payload: dict[str, Any]) -> None:
    payload.pop("thread", None)
    candidates = [payload.get("message")]
    chat_payload = payload.get("chat")
    if isinstance(chat_payload, dict):
        message_payload = chat_payload.get("messagePayload")
        if isinstance(message_payload, dict):
            candidates.append(message_payload.get("message"))
        command_payload = chat_payload.get("appCommandPayload")
        if isinstance(command_payload, dict):
            candidates.append(command_payload.get("message"))
    for message in candidates:
        if isinstance(message, dict):
            message.pop("thread", None)


def _has_visible_google_chat_response(data: dict[str, Any]) -> bool:
    if not data:
        return False

    text = data.get("text")
    if isinstance(text, str) and text.strip():
        return True

    return any(
        data.get(key)
        for key in (
            "cards",
            "cardsV2",
            "accessoryWidgets",
            "actionResponse",
            "hostAppDataAction",
        )
    )


def _build_forward_payload(payload: dict[str, Any], event: NormalizedChatEvent, decision: PolicyDecision) -> dict[str, Any]:
    """Forward the original Google Chat event plus router policy context.

    OpenClaw's Google Chat channel still receives the normal event shape it expects.
    The `_lyraRouter` extension is additive and namespaced so it won't affect Google
    Chat response parsing, but keeps the policy decision available for audit/debug.
    """
    forwarded = deepcopy(payload)
    _strip_thread_delivery_context(forwarded)
    forwarded["_lyraRouter"] = {
        "source": "googlechat",
        "space": event.space_name,
        "user": event.user_name,
        "thread": None,
        "policy": decision.policy_key,
        "allowed_scope": decision.scope,
        "message": event.text,
        "tool_mode": "restricted" if decision.scope != "general_owner_only" else "normal",
        "forbidden_actions": [
            "campaign_change",
            "budget_change",
            "deploy",
            "tag_change",
        ],
        "decision": decision.decision,
        "intent": decision.intent.value,
        "reason": decision.reason,
        "continuation": decision.continuation,
        "reply_mode": "root_only",
    }
    return forwarded


def _post_to_openclaw(
    *,
    settings: Settings,
    payload: dict[str, Any],
    authorization: str | None,
) -> dict[str, Any]:
    if not settings.openclaw_forward_url:
        raise OpenClawForwardError("OpenClaw forward URL is not configured")

    headers = {"Content-Type": "application/json"}
    if authorization:
        headers["Authorization"] = authorization

    response = requests.post(
        settings.openclaw_forward_url,
        json=payload,
        headers=headers,
        timeout=settings.openclaw_forward_timeout_seconds,
    )

    if response.status_code >= 400:
        raise OpenClawForwardError(
            f"OpenClaw returned HTTP {response.status_code}: {response.text[:300]}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise OpenClawForwardError("OpenClaw returned a non-JSON response") from exc

    if not isinstance(data, dict):
        raise OpenClawForwardError("OpenClaw returned an unexpected response shape")
    return data


async def forward_to_openclaw(
    *,
    settings: Settings,
    payload: dict[str, Any],
    event: NormalizedChatEvent,
    decision: PolicyDecision,
    authorization: str | None,
) -> dict[str, Any]:
    forwarded_payload = _build_forward_payload(payload, event, decision)
    try:
        return await run_in_threadpool(
            _post_to_openclaw,
            settings=settings,
            payload=forwarded_payload,
            authorization=authorization,
        )
    except OpenClawForwardError:
        raise
    except Exception as exc:  # pragma: no cover - defensive network boundary
        logger.exception("openclaw_forward_failed")
        raise OpenClawForwardError("OpenClaw forward failed") from exc
