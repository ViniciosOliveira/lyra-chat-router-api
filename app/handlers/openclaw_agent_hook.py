import logging
import re
from typing import Any

import requests
from fastapi.concurrency import run_in_threadpool

from app.core.config import Settings
from app.googlechat.schemas import NormalizedChatEvent
from app.policies.engine import PolicyDecision

logger = logging.getLogger(__name__)


class OpenClawAgentHookError(RuntimeError):
    pass


def _rules_for_space(event: NormalizedChatEvent, decision: PolicyDecision) -> str:
    if decision.scope == "marketing_performance_analysis_only":
        return """- Comitê de Mkt Performance is analysis-only.
- You may analyze, diagnose, explain metrics, produce reports and recommendations.
- You must not execute campaign, budget, tag, pixel, code, deploy, permission, or external-send changes.
- If the user asks for execution, refuse briefly and offer analysis/recommendation instead."""

    if decision.scope == "dev_owner_only":
        return """- Dev / Mission Control is an operational development space for Vinícios.
- If Vinícios explicitly authorizes execution (for example: "pode seguir"), you may inspect code, edit files, run tests/builds, commit, deploy, and validate according to the project documentation.
- Before technical action, identify the system named by the user and load the relevant docs/memory first.
- Do not apply the Marketing Performance analysis-only restriction in this space."""

    if decision.scope == "turnstile_only":
        return """- This space is restricted to Control iD turnstile operations only.
- Load the turnstile skill/documentation before acting.
- Refuse anything unrelated to turnstile control."""

    if decision.scope == "certificates_correios_only":
        return """- This space is restricted to certificate signing and Correios label generation.
- Load the matching operational skill before acting.
- Refuse anything outside certificates or Correios labels."""

    if decision.scope == "general_owner_only":
        return """- This is an owner-only space for Vinícios.
- Follow the normal Lyra/OpenClaw rules for the requested task.
- Load relevant docs before technical, operational, external, or destructive actions."""

    return f"""- Scope from policy: {decision.scope}.
- Follow the policy scope above and the normal Lyra/OpenClaw safety/documentation rules.
- If the scope is unclear, stop and ask for clarification instead of guessing."""


def _timeout_seconds_for_space(*, settings: Settings, decision: PolicyDecision) -> int:
    if decision.scope == "dev_owner_only":
        return max(settings.openclaw_agent_hook_timeout_seconds, 900)
    return settings.openclaw_agent_hook_timeout_seconds


def _build_agent_message(event: NormalizedChatEvent, decision: PolicyDecision) -> str:
    rules = _rules_for_space(event, decision)

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
{rules}

User message:
{event.text}
""".strip()


def _session_key_component(value: str | None, fallback: str) -> str:
    raw = (value or fallback).strip().lower()
    return re.sub(r"[^a-z0-9:/._-]+", "-", raw).strip("-") or fallback


def build_session_key(*, settings: Settings, event: NormalizedChatEvent) -> str:
    """Build a stable OpenClaw hook session key scoped by Google Chat space.

    Use one session per space instead of one session per thread/message. This
    keeps group continuity while preventing Pub/Sub traffic from falling into
    the main session.
    """
    prefix = settings.openclaw_agent_hook_session_key_prefix.rstrip(":")
    space = _session_key_component(event.space_name, "unknown-space")
    return f"{prefix}:{space}"


def _post_agent_hook(*, settings: Settings, event: NormalizedChatEvent, decision: PolicyDecision) -> dict[str, Any]:
    if not settings.openclaw_agent_hook_url:
        raise OpenClawAgentHookError("OpenClaw agent hook URL is not configured")
    if not settings.openclaw_agent_hook_token:
        raise OpenClawAgentHookError("OpenClaw agent hook token is not configured")

    payload: dict[str, Any] = {
        "message": _build_agent_message(event, decision),
        "name": "Google Chat Pub/Sub",
        "agentId": settings.openclaw_agent_hook_agent_id,
        "sessionKey": build_session_key(settings=settings, event=event),
        "deliver": True,
        "channel": "googlechat",
        "to": event.space_name,
        "timeoutSeconds": _timeout_seconds_for_space(settings=settings, decision=decision),
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
