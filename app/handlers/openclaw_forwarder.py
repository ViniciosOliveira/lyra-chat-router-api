from app.googlechat.schemas import NormalizedChatEvent
from app.policies.engine import PolicyDecision


def build_openclaw_forward_payload(event: NormalizedChatEvent, decision: PolicyDecision) -> dict:
    return {
        "source": "googlechat",
        "space": event.space_name,
        "user": event.user_name,
        "thread": event.thread_name,
        "policy": decision.policy_key,
        "allowed_scope": "analysis_only",
        "message": event.text,
        "tool_mode": "restricted",
        "forbidden_actions": ["campaign_change", "budget_change", "deploy", "tag_change"],
    }
