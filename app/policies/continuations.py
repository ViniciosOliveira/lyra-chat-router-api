import logging
import re
import unicodedata
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.session import get_engine
from app.googlechat.schemas import NormalizedChatEvent
from app.policies.intents import Intent

logger = logging.getLogger(__name__)

CONTINUATION_REASON = "Affirmative confirmation continues previous scoped operation"
CONTINUATION_TTL = timedelta(minutes=15)
SCOPED_CONTINUATION_INTENTS = {
    Intent.CERTIFICATE_SIGNING,
    Intent.CORREIOS_LABEL,
}

_AFFIRMATIVE_CONFIRMATIONS = {
    "autorizado",
    "confirmo",
    "ok",
    "pode",
    "pode executar",
    "pode fazer",
    "pode seguir",
    "sim",
    "sim pode",
    "sim pode executar",
    "sim pode fazer",
    "sim pode seguir",
}


def _normalize_confirmation(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.lower().strip()
    normalized = re.sub(r"^(?:@\s*lyra|<users/[^>]+>)\s*", "", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def is_affirmative_confirmation(value: str | None) -> bool:
    return _normalize_confirmation(value) in _AFFIRMATIVE_CONFIRMATIONS


class ConfirmationContinuationResolver:
    """Resolve a short confirmation against a recent scoped request.

    The lookup is deliberately strict: same space, Google Chat thread and user,
    within a short time window. A successful continuation consumes the pending
    request so a second confirmation cannot replay it.
    """

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine if engine is not None else get_engine()

    def resolve(self, event: NormalizedChatEvent) -> Intent | None:
        if not is_affirmative_confirmation(event.text):
            return None
        if not self._engine or not event.space_name or not event.thread_name or not event.user_name:
            return None

        try:
            with self._engine.begin() as conn:
                rows = conn.execute(
                    text(
                        """
                        SELECT
                            re.classified_intent,
                            re.handler,
                            re.decision,
                            re.reason,
                            m.text AS message_text
                        FROM routing_events re
                        JOIN messages m ON m.id = re.message_id
                        JOIN spaces s ON s.id = m.space_id
                        JOIN users u ON u.id = m.user_id
                        WHERE s.space_name = :space_name
                          AND u.google_user_name = :user_name
                          AND m.thread_name = :thread_name
                          AND re.created_at >= now() - :ttl
                        ORDER BY re.created_at DESC
                        LIMIT 20
                        """
                    ),
                    {
                        "space_name": event.space_name,
                        "user_name": event.user_name,
                        "thread_name": event.thread_name,
                        "ttl": CONTINUATION_TTL,
                    },
                ).mappings().all()
        except Exception:
            logger.exception("confirmation_continuation_lookup_failed")
            return None

        for row in rows:
            if is_affirmative_confirmation(row.get("message_text")):
                if row.get("reason") == CONTINUATION_REASON:
                    return None
                continue

            if row.get("decision") != "allow" or row.get("handler") != "scoped_operation_handler":
                return None

            try:
                intent = Intent(str(row.get("classified_intent")))
            except ValueError:
                return None
            return intent if intent in SCOPED_CONTINUATION_INTENTS else None

        return None
