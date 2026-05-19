import logging
from typing import Any

import requests
from fastapi.concurrency import run_in_threadpool

from app.core.config import Settings
from app.googlechat.schemas import NormalizedChatEvent
from app.policies.engine import PolicyDecision

logger = logging.getLogger(__name__)


class OpenClawAgentHookError(RuntimeError):
    pass


def _build_agent_message(event: NormalizedChatEvent, decision: PolicyDecision) -> str:
    return f"""Google Chat message received via Lyra Chat Router Pub/Sub subscription.

Context:
- Space: {event.space_name}
- User: {event.user_name} ({event.user_display_name or 'unknown'})
- Thread: {event.thread_name or 'unknown'}
- Policy: {decision.policy_key}
- Scope: {decision.scope}
- Intent: {decision.intent.value}
- Decision: {decision.decision}
- Reason: {decision.reason}

Rules for this space:
- Comitê de Mkt Performance is analysis-only.
- You may analyze, diagnose, explain metrics, produce reports and recommendations.
- You must not execute campaign, budget, tag, pixel, code, deploy, permission, or external-send changes.
- If the user asks for execution, refuse briefly and offer analysis/recommendation instead.

User message:
{event.text}
""".strip()


def _post_agent_hook(*, settings: Settings, event: NormalizedChatEvent, decision: PolicyDecision) -> dict[str, Any]:
    if not settings.openclaw_agent_hook_url:
        raise OpenClawAgentHookError("OpenClaw agent hook URL is not configured")
    if not settings.openclaw_agent_hook_token:
        raise OpenClawAgentHookError("OpenClaw agent hook token is not configured")

    payload: dict[str, Any] = {
        "message": _build_agent_message(event, decision),
        "name": "Google Chat Pub/Sub",
        "agentId": settings.openclaw_agent_hook_agent_id,
        "deliver": True,
        "channel": "googlechat",
        "to": event.space_name,
        "timeoutSeconds": settings.openclaw_agent_hook_timeout_seconds,
    }
    if event.thread_name:
        payload["threadId"] = event.thread_name

    response = requests.post(
        settings.openclaw_agent_hook_url,
        json=payload,
        headers={
            "Authorization": f"Bearer {settings.openclaw_agent_hook_token}",
            "Content-Type": "application/json",
        },
        timeout=settings.openclaw_agent_hook_request_timeout_seconds,
    )
    if response.status_code >= 400:
        raise OpenClawAgentHookError(
            f"OpenClaw agent hook returned HTTP {response.status_code}: {response.text[:300]}"
        )
    try:
        data = response.json()
    except ValueError:
        data = {"status": "accepted"}
    if not isinstance(data, dict):
        return {"status": "accepted", "raw_type": type(data).__name__}
    return data


async def enqueue_openclaw_agent_turn(
    *, settings: Settings, event: NormalizedChatEvent, decision: PolicyDecision
) -> dict[str, Any]:
    try:
        return await run_in_threadpool(
            _post_agent_hook,
            settings=settings,
            event=event,
            decision=decision,
        )
    except OpenClawAgentHookError:
        raise
    except Exception as exc:  # pragma: no cover - defensive network boundary
        logger.exception("openclaw_agent_hook_failed")
        raise OpenClawAgentHookError("OpenClaw agent hook failed") from exc
