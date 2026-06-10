from fastapi import APIRouter, Depends, Header, Request

from app.audit.logger import AuditLogger
from app.core.config import Settings, get_settings
from app.delivery.ledger import DeliveryLedger
from app.googlechat.auth import verify_google_chat_authorization
from app.googlechat.normalizer import normalize_event
from app.handlers.analytics import build_analytics_response
from app.handlers.deny import build_deny_response
from app.handlers.direct_reply import build_direct_reply
from app.handlers.openclaw_agent_hook import (
    OpenClawAgentHookError,
    enqueue_openclaw_forward_fallback,
    notify_owner_about_out_of_scope,
    should_escalate_to_owner,
)
from app.handlers.openclaw_forward import OpenClawForwardError, forward_to_openclaw
from app.handlers.scoped_operation import build_scoped_operation_response
from app.policies.engine import PolicyEngine

router = APIRouter(prefix="/googlechat", tags=["googlechat"])


def _is_workspace_addon_chat_event(payload: dict) -> bool:
    chat_payload = payload.get("chat") or {}
    return bool(chat_payload.get("messagePayload") or chat_payload.get("appCommandPayload"))


def _format_google_chat_response(payload: dict, response: dict) -> dict:
    if not _is_workspace_addon_chat_event(payload):
        return response

    return {
        "hostAppDataAction": {
            "chatDataAction": {
                "createMessageAction": {
                    "message": response,
                }
            }
        }
    }


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "service": settings.app_name}


@router.post("", response_model=None)
@router.post("/", response_model=None)
async def receive_google_chat_event(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> dict:
    await verify_google_chat_authorization(settings=settings, authorization=authorization)
    payload = await request.json()
    event = normalize_event(payload)
    delivery_ledger = DeliveryLedger()
    delivery_state = delivery_ledger.record_received(event)
    if delivery_state.already_completed:
        return {}

    decision = PolicyEngine().decide(event)

    if decision.handler == "deny_handler":
        response = build_deny_response(decision)
        if settings.openclaw_agent_hook_enabled and should_escalate_to_owner(decision):
            try:
                await notify_owner_about_out_of_scope(settings=settings, event=event, decision=decision)
            except OpenClawAgentHookError:
                # Best-effort escalation: never break the user-visible denial response.
                pass
    elif settings.openclaw_forward_enabled:
        try:
            delivery_ledger.mark_forwarding(delivery_state.provider_message_id)
            response = await forward_to_openclaw(
                settings=settings,
                payload=payload,
                event=event,
                decision=decision,
                authorization=authorization,
            )
            if response:
                delivery_ledger.mark_delivered(delivery_state.provider_message_id, response)
            else:
                delivery_ledger.mark_forwarded(delivery_state.provider_message_id, response)
            AuditLogger().record_routing(event=event, decision=decision, response=response)
            return response
        except OpenClawForwardError as exc:
            fallback_response = None
            delivery_ledger.mark_retry_pending(delivery_state.provider_message_id, error=str(exc))
            if settings.openclaw_agent_hook_enabled:
                try:
                    fallback_response = await enqueue_openclaw_forward_fallback(
                        settings=settings,
                        event=event,
                        decision=decision,
                    )
                    delivery_ledger.mark_fallback_queued(
                        delivery_state.provider_message_id,
                        fallback_response,
                    )
                except OpenClawAgentHookError:
                    fallback_response = {"status": "failed"}
            AuditLogger().record_routing(
                event=event,
                decision=decision,
                response={
                    "status": "no_content",
                    "reason": "openclaw_forward_failed",
                    "fallback": fallback_response or {"status": "disabled"},
                },
            )
            return {}
    elif decision.handler == "analytics_handler":
        response = build_analytics_response(event, decision)
    elif decision.handler == "scoped_operation_handler":
        response = build_scoped_operation_response(event, decision)
    else:
        response = build_direct_reply(event)

    delivery_ledger.mark_delivered(delivery_state.provider_message_id, response)
    AuditLogger().record_routing(event=event, decision=decision, response=response)
    return _format_google_chat_response(payload, response)
