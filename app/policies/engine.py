from dataclasses import dataclass

from app.googlechat.schemas import NormalizedChatEvent
from app.policies.intents import Intent, classify_intent
from app.policies.registry import MKT_PERFORMANCE_POLICY_KEY, SpacePolicy, get_space_policy

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

TURNSTILE_INTENTS = {Intent.TURNSTILE_CONTROL}
CERTIFICATE_CORREIOS_INTENTS = {Intent.CERTIFICATE_SIGNING, Intent.CORREIOS_LABEL}


@dataclass(frozen=True)
class PolicyDecision:
    policy_key: str
    intent: Intent
    decision: str
    handler: str
    reason: str
    scope: str = "unknown"


class PolicyEngine:
    def decide(self, event: NormalizedChatEvent) -> PolicyDecision:
        intent = classify_intent(event.text)
        policy = get_space_policy(event.space_name)

        if policy is None:
            return PolicyDecision(
                policy_key="unknown_space",
                intent=intent,
                decision="deny",
                handler="deny_handler",
                reason="Space is not configured in Lyra Chat Router",
            )

        if not self._is_allowed_user(policy, event.user_name):
            return PolicyDecision(
                policy_key=policy.key,
                intent=intent,
                decision="deny",
                handler="deny_handler",
                reason="User is not allowed for this Google Chat space",
                scope=policy.scope,
            )

        if policy.key == MKT_PERFORMANCE_POLICY_KEY:
            return self._decide_mkt_performance(intent, policy)

        if policy.scope == "turnstile_only":
            return self._decide_scoped_operation(
                intent=intent,
                policy=policy,
                allowed_intents=TURNSTILE_INTENTS,
                deny_reason="Only turnstile control requests are allowed in this space",
            )

        if policy.scope == "certificates_correios_only":
            return self._decide_scoped_operation(
                intent=intent,
                policy=policy,
                allowed_intents=CERTIFICATE_CORREIOS_INTENTS,
                deny_reason="Only certificate signing and Correios label requests are allowed in this space",
            )

        # Owner-only DM/dev/test spaces are allowed through the router. Execution remains
        # handled by downstream handlers in later phases; this prevents the global cutover
        # from falling into default_safe for already configured spaces.
        return PolicyDecision(
            policy_key=policy.key,
            intent=intent,
            decision="allow",
            handler="direct_reply",
            reason="Configured owner-only Google Chat space",
            scope=policy.scope,
        )

    @staticmethod
    def _is_allowed_user(policy: SpacePolicy, user_name: str | None) -> bool:
        return bool(user_name and user_name in policy.allowed_users)

    @staticmethod
    def _decide_mkt_performance(intent: Intent, policy: SpacePolicy) -> PolicyDecision:
        if intent in BLOCKED_MKT_INTENTS:
            return PolicyDecision(
                policy_key=policy.key,
                intent=intent,
                decision="deny",
                handler="deny_handler",
                reason="Operational execution is blocked in Mkt Performance group",
                scope=policy.scope,
            )
        if intent in ALLOWED_MKT_INTENTS:
            return PolicyDecision(
                policy_key=policy.key,
                intent=intent,
                decision="allow",
                handler="analytics_handler" if intent != Intent.UNKNOWN else "direct_reply",
                reason="Analysis/reporting scope allowed",
                scope=policy.scope,
            )
        return PolicyDecision(
            policy_key=policy.key,
            intent=intent,
            decision="deny",
            handler="deny_handler",
            reason="Intent is outside Mkt Performance analysis scope",
            scope=policy.scope,
        )

    @staticmethod
    def _decide_scoped_operation(
        intent: Intent,
        policy: SpacePolicy,
        allowed_intents: set[Intent],
        deny_reason: str,
    ) -> PolicyDecision:
        if intent in allowed_intents:
            return PolicyDecision(
                policy_key=policy.key,
                intent=intent,
                decision="allow",
                handler="scoped_operation_handler",
                reason="Intent matches configured operational scope",
                scope=policy.scope,
            )
        return PolicyDecision(
            policy_key=policy.key,
            intent=intent,
            decision="deny",
            handler="deny_handler",
            reason=deny_reason,
            scope=policy.scope,
        )
