from dataclasses import dataclass

from app.googlechat.schemas import NormalizedChatEvent
from app.policies.defaults import MKT_PERFORMANCE_POLICY_KEY, MKT_PERFORMANCE_SPACE
from app.policies.intents import Intent, classify_intent

ALLOWED_MKT_INTENTS = {
    Intent.MARKETING_ANALYSIS,
    Intent.PERFORMANCE_REPORT,
    Intent.TRACKING_DIAGNOSIS,
    Intent.METRIC_EXPLANATION,
    Intent.RECOMMENDATION,
    Intent.UNKNOWN,  # Unknown stays safe: direct reply asks for clarification, no execution.
}

BLOCKED_MKT_INTENTS = {
    Intent.CAMPAIGN_CHANGE,
    Intent.BUDGET_CHANGE,
    Intent.TAG_CHANGE,
    Intent.PIXEL_CHANGE,
    Intent.CODE_CHANGE,
    Intent.DEPLOY,
    Intent.EXTERNAL_MESSAGE_SEND,
    Intent.UNKNOWN_OPERATIONAL_EXECUTION,
}


@dataclass(frozen=True)
class PolicyDecision:
    policy_key: str
    intent: Intent
    decision: str
    handler: str
    reason: str


class PolicyEngine:
    def decide(self, event: NormalizedChatEvent) -> PolicyDecision:
        intent = classify_intent(event.text)

        if event.space_name == MKT_PERFORMANCE_SPACE:
            if intent in BLOCKED_MKT_INTENTS:
                return PolicyDecision(
                    policy_key=MKT_PERFORMANCE_POLICY_KEY,
                    intent=intent,
                    decision="deny",
                    handler="deny_handler",
                    reason="Operational execution is blocked in Mkt Performance group",
                )
            if intent in ALLOWED_MKT_INTENTS:
                return PolicyDecision(
                    policy_key=MKT_PERFORMANCE_POLICY_KEY,
                    intent=intent,
                    decision="allow",
                    handler="analytics_handler" if intent != Intent.UNKNOWN else "direct_reply",
                    reason="Analysis/reporting scope allowed",
                )

        return PolicyDecision(
            policy_key="default_safe",
            intent=intent,
            decision="deny",
            handler="deny_handler",
            reason="No active policy for this space",
        )
