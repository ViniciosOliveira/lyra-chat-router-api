import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from app.audit.redaction import redact
from app.db.session import get_engine
from app.googlechat.schemas import NormalizedChatEvent


@dataclass(frozen=True)
class DeliveryState:
    mode: str
    provider_message_id: str
    status: str
    stage: str
    attempt_count: int = 0
    duplicate_count: int = 0

    @property
    def already_completed(self) -> bool:
        return self.duplicate_count > 0 and self.status in {"delivered", "forwarded"}


def _provider_message_id(event: NormalizedChatEvent) -> str:
    if event.message_name:
        return event.message_name
    return f"synthetic:{uuid4()}"


def _json_payload(payload: Any) -> str:
    return json.dumps(redact(payload or {}))


class DeliveryLedger:
    def __init__(self) -> None:
        self._engine = get_engine()

    def record_received(self, event: NormalizedChatEvent) -> DeliveryState:
        provider_message_id = _provider_message_id(event)
        if self._engine is None:
            return DeliveryState(
                mode="no_database",
                provider_message_id=provider_message_id,
                status="received",
                stage="received",
            )

        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO delivery_ledger (
                        provider_message_id, space_name, user_name, thread_name,
                        message_text, status, stage, request_redacted
                    )
                    VALUES (
                        :provider_message_id, :space_name, :user_name, :thread_name,
                        :message_text, 'received', 'received', CAST(:request_redacted AS jsonb)
                    )
                    ON CONFLICT (provider_message_id) DO UPDATE SET
                        duplicate_count = delivery_ledger.duplicate_count + 1,
                        updated_at = now()
                    RETURNING
                        provider_message_id, status, stage, attempt_count, duplicate_count
                    """
                ),
                {
                    "provider_message_id": provider_message_id,
                    "space_name": event.space_name,
                    "user_name": event.user_name,
                    "thread_name": event.thread_name,
                    "message_text": event.text,
                    "request_redacted": _json_payload(event.raw),
                },
            ).mappings().one()

        return DeliveryState(mode="database", **dict(row))

    def mark_forwarding(self, provider_message_id: str) -> None:
        self._update(
            provider_message_id,
            """
            status = 'forwarding',
            stage = 'openclaw_forwarding',
            attempt_count = attempt_count + 1,
            forwarding_started_at = now(),
            updated_at = now()
            """,
        )

    def mark_delivered(self, provider_message_id: str, response: dict[str, Any]) -> None:
        self._update(
            provider_message_id,
            """
            status = 'delivered',
            stage = 'googlechat_sync_response',
            response_redacted = CAST(:response_redacted AS jsonb),
            delivered_at = now(),
            next_retry_at = NULL,
            updated_at = now()
            """,
            response_redacted=_json_payload(response),
        )

    def mark_forwarded(self, provider_message_id: str, response: dict[str, Any]) -> None:
        self._update(
            provider_message_id,
            """
            status = 'forwarded',
            stage = 'openclaw_forward_accepted',
            response_redacted = CAST(:response_redacted AS jsonb),
            forwarded_at = now(),
            next_retry_at = NULL,
            updated_at = now()
            """,
            response_redacted=_json_payload(response),
        )

    def mark_retry_pending(
        self,
        provider_message_id: str,
        *,
        error: str,
        retry_after_seconds: int = 60,
    ) -> None:
        self._update(
            provider_message_id,
            """
            status = 'retry_pending',
            stage = 'openclaw_forward_failed',
            last_error = :error,
            failed_at = now(),
            next_retry_at = now() + (:retry_after_seconds * interval '1 second'),
            updated_at = now()
            """,
            error=error[:1000],
            retry_after_seconds=retry_after_seconds,
        )

    def mark_fallback_queued(self, provider_message_id: str, response: dict[str, Any]) -> None:
        self._update(
            provider_message_id,
            """
            status = 'retry_pending',
            stage = 'openclaw_fallback_queued',
            response_redacted = CAST(:response_redacted AS jsonb),
            next_retry_at = NULL,
            updated_at = now()
            """,
            response_redacted=_json_payload(response),
        )

    def list_stale(self, *, older_than_seconds: int = 120, limit: int = 50) -> list[dict[str, Any]]:
        if self._engine is None:
            return []

        safe_limit = max(1, min(limit, 200))
        with self._engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                        provider_message_id, space_name, user_name, thread_name,
                        status, stage, attempt_count, duplicate_count, last_error,
                        received_at, forwarding_started_at, next_retry_at, updated_at
                    FROM delivery_ledger
                    WHERE
                        (
                            status IN ('received', 'forwarding')
                            AND updated_at < now() - (:older_than_seconds * interval '1 second')
                        )
                        OR (
                            status = 'retry_pending'
                            AND (next_retry_at IS NULL OR next_retry_at <= now())
                        )
                    ORDER BY updated_at ASC
                    LIMIT :limit
                    """
                ),
                {"older_than_seconds": older_than_seconds, "limit": safe_limit},
            ).mappings().all()

        return [dict(row) for row in rows]

    def mark_alerted(self, provider_message_ids: list[str]) -> int:
        if self._engine is None or not provider_message_ids:
            return 0

        with self._engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    UPDATE delivery_ledger
                    SET
                        alert_count = alert_count + 1,
                        last_alerted_at = now(),
                        updated_at = now()
                    WHERE provider_message_id = ANY(:provider_message_ids)
                    """
                ),
                {"provider_message_ids": provider_message_ids},
            )
        return int(result.rowcount or 0)

    def _update(self, provider_message_id: str, assignments: str, **params: Any) -> None:
        if self._engine is None:
            return

        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    UPDATE delivery_ledger
                    SET {assignments}
                    WHERE provider_message_id = :provider_message_id
                    """
                ),
                {"provider_message_id": provider_message_id, **params},
            )

