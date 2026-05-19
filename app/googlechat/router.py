from fastapi import APIRouter, Depends, Header, Request

from app.audit.logger import AuditLogger
from app.core.config import Settings, get_settings
from app.googlechat.auth import verify_google_chat_authorization
from app.googlechat.normalizer import normalize_event
from app.handlers.analytics import build_analytics_response
from app.handlers.deny import build_deny_response
from app.handlers.direct_reply import build_direct_reply
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


@router.post("")
@router.post("/")
async def receive_google_chat_event(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> dict:
    await verify_google_chat_authorization(settings=settings, authorization=authorization)
    payload = await request.json()
    event = normalize_event(payload)
    decision = PolicyEngine().decide(event)

    if decision.handler == "deny_handler":
        response = build_deny_response(decision)
    elif decision.handler == "analytics_handler":
        response = build_analytics_response(event, decision)
    elif decision.handler == "scoped_operation_handler":
        response = build_scoped_operation_response(event, decision)
    else:
        response = build_direct_reply(event)

    AuditLogger().record_routing(event=event, decision=decision, response=response)
    return _format_google_chat_response(payload, response)
