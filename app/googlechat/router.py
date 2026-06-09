from typing import Any

from fastapi import APIRouter, Depends, Header, Request, Response

from app.audit.logger import AuditLogger
from app.core.config import Settings, get_settings
from app.googlechat.auth import verify_google_chat_authorization
from app.googlechat.normalizer import normalize_event
from app.handlers.analytics import build_analytics_response
from app.handlers.deny import build_deny_response
from app.handlers.direct_reply import build_direct_reply
from app.handlers.openclaw_agent_hook import OpenClawAgentHookError, notify_owner_about_out_of_scope, should_escalate_to_owner
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
) -> Any:
    await verify_google_chat_authorization(settings=settings, authorization=authorization)
    payload = await request.json()
    event = normalize_event(payload)
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
            response = await forward_to_openclaw(
                settings=settings,
                payload=payload,
                event=event,
                decision=decision,
                authorization=authorization,
            )
            AuditLogger().record_routing(event=event, decision=decision, response=response)
            return response
        except OpenClawForwardError:
            AuditLogger().record_routing(
                event=event,
                decision=decision,
                response={"status": "no_content", "reason": "openclaw_forward_failed"},
            )
            return Response(status_code=204)
    elif decision.handler == "analytics_handler":
        response = build_analytics_response(event, decision)
    elif decision.handler == "scoped_operation_handler":
        response = build_scoped_operation_response(event, decision)
    else:
        response = build_direct_reply(event)

    AuditLogger().record_routing(event=event, decision=decision, response=response)
    return _format_google_chat_response(payload, response)
