import logging
from time import perf_counter
from typing import Any

from sqlalchemy import text

from app.audit.redaction import redact
from app.db.session import get_engine
from app.googlechat.schemas import NormalizedChatEvent
from app.policies.engine import PolicyDecision

logger = logging.getLogger(__name__)


class AuditLogger:
    def __init__(self) -> None:
        self._started_at = perf_counter()
        self._engine = get_engine()

    def record_routing(
        self,
        *,
        event: NormalizedChatEvent,
        decision: PolicyDecision,
        response: dict[str, Any],
    ) -> None:
        latency_ms = int((perf_counter() - self._started_at) * 1000)
        payload_redacted = redact(event.raw)
        response_redacted = redact(response)

        if self._engine is None:
            logger.info(
                "routing_decision",
                extra={
                    "space_name": event.space_name,
                    "user_name": event.user_name,
                    "message_name": event.message_name,
                    "intent": decision.intent.value,
                    "decision": decision.decision,
                    "handler": decision.handler,
                    "latency_ms": latency_ms,
                },
            )
            return

        with self._engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    WITH upsert_policy AS (
                        SELECT id FROM policies WHERE key = :policy_key
                    ), upsert_space AS (
                        INSERT INTO spaces (space_name, display_name, space_type, default_policy_id)
                        VALUES (:space_name, :space_display_name, :space_type, (SELECT id FROM upsert_policy))
                        ON CONFLICT (space_name) DO UPDATE SET
                            display_name = EXCLUDED.display_name,
                            updated_at = now()
                        RETURNING id
                    ), upsert_user AS (
                        INSERT INTO users (google_user_name, email, display_name, status)
                        VALUES (:user_name, :user_email, :user_display_name, 'active')
                        ON CONFLICT (google_user_name) DO UPDATE SET
                            email = EXCLUDED.email,
                            display_name = EXCLUDED.display_name,
                            updated_at = now()
                        RETURNING id
                    ), inserted_message AS (
                        INSERT INTO messages (
                            provider_message_id, space_id, user_id, thread_name,
                            direction, event_type, text, payload_redacted
                        )
                        SELECT
                            :provider_message_id,
                            (SELECT id FROM upsert_space),
                            (SELECT id FROM upsert_user),
                            :thread_name,
                            'inbound',
                            :event_type,
                            :message_text,
                            CAST(:payload_redacted AS jsonb)
                        RETURNING id
                    ), inserted_route AS (
                        INSERT INTO routing_events (
                            message_id, policy_id, classified_intent, handler,
                            decision, reason, latency_ms
                        )
                        SELECT
                            (SELECT id FROM inserted_message),
                            (SELECT id FROM upsert_policy),
                            :classified_intent,
                            :handler,
                            :decision,
                            :reason,
                            :latency_ms
                        RETURNING id
                    )
                    INSERT INTO handler_runs (
                        routing_event_id, handler, status,
                        request_redacted, response_redacted, started_at, finished_at
                    )
                    SELECT
                        (SELECT id FROM inserted_route),
                        :handler,
                        'success',
                        CAST(:payload_redacted AS jsonb),
                        CAST(:response_redacted AS jsonb),
                        now(),
                        now()
                    RETURNING id
                    """
                ),
                {
                    "policy_key": decision.policy_key,
                    "space_name": event.space_name or "unknown",
                    "space_display_name": event.space_display_name,
                    "space_type": "dm" if (event.space_name or "").startswith("spaces/DM") else "group",
                    "user_name": event.user_name or "unknown",
                    "user_email": event.user_email,
                    "user_display_name": event.user_display_name,
                    "provider_message_id": event.message_name,
                    "thread_name": event.thread_name,
                    "event_type": event.event_type,
                    "message_text": event.text,
                    "payload_redacted": __import__("json").dumps(payload_redacted),
                    "response_redacted": __import__("json").dumps(response_redacted),
                    "classified_intent": decision.intent.value,
                    "handler": decision.handler,
                    "decision": decision.decision,
                    "reason": decision.reason,
                    "latency_ms": latency_ms,
                },
            )
            result.scalar_one()
