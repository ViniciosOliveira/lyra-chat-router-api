from unittest.mock import MagicMock

from app.googlechat.schemas import NormalizedChatEvent
from app.policies.continuations import (
    CONTINUATION_REASON,
    ConfirmationContinuationResolver,
    is_affirmative_confirmation,
)
from app.policies.intents import Intent


def event(text: str = "@Lyra Sim") -> NormalizedChatEvent:
    return NormalizedChatEvent(
        event_type="MESSAGE",
        space_name="spaces/AAQAqhVlskk",
        space_display_name="Comitê - Operações Educacionais",
        user_name="users/102836791593473492239",
        user_display_name="Daiane",
        user_email=None,
        thread_name="spaces/AAQAqhVlskk/threads/labels",
        message_name="spaces/AAQAqhVlskk/messages/confirmation",
        text=text,
        raw={},
    )


def engine_with_rows(rows: list[dict]) -> MagicMock:
    engine = MagicMock()
    result = engine.begin.return_value.__enter__.return_value.execute.return_value
    result.mappings.return_value.all.return_value = rows
    return engine


def test_recognizes_conservative_affirmative_variants():
    assert is_affirmative_confirmation("@Lyra Sim")
    assert is_affirmative_confirmation("sim, pode seguir")
    assert is_affirmative_confirmation("Pode executar")
    assert not is_affirmative_confirmation("sim, mas primeiro altere o endereço")
    assert not is_affirmative_confirmation("bom dia")


def test_non_confirmation_does_not_query_database():
    engine = engine_with_rows([])

    assert ConfirmationContinuationResolver(engine).resolve(event("bom dia")) is None
    engine.begin.assert_not_called()


def test_resolves_recent_scoped_request_after_old_denied_confirmation():
    engine = engine_with_rows(
        [
            {
                "classified_intent": "unknown",
                "handler": "deny_handler",
                "decision": "deny",
                "reason": "Intent is outside scope",
                "message_text": "@Lyra Sim",
            },
            {
                "classified_intent": "correios_label",
                "handler": "scoped_operation_handler",
                "decision": "allow",
                "reason": "Education operations are allowed",
                "message_text": "@Lyra Gerar etiquetas dos certificados",
            },
        ]
    )

    resolved = ConfirmationContinuationResolver(engine).resolve(event())

    assert resolved == Intent.CORREIOS_LABEL
    params = engine.begin.return_value.__enter__.return_value.execute.call_args.args[1]
    assert params["space_name"] == "spaces/AAQAqhVlskk"
    assert params["thread_name"] == "spaces/AAQAqhVlskk/threads/labels"
    assert params["user_name"] == "users/102836791593473492239"


def test_successful_continuation_consumes_pending_request():
    engine = engine_with_rows(
        [
            {
                "classified_intent": "correios_label",
                "handler": "scoped_operation_handler",
                "decision": "allow",
                "reason": CONTINUATION_REASON,
                "message_text": "@Lyra Sim",
            }
        ]
    )

    assert ConfirmationContinuationResolver(engine).resolve(event()) is None


def test_latest_substantive_message_must_be_a_scoped_operation():
    engine = engine_with_rows(
        [
            {
                "classified_intent": "unknown",
                "handler": "deny_handler",
                "decision": "deny",
                "reason": "Outside scope",
                "message_text": "mude o endereço antes",
            },
            {
                "classified_intent": "correios_label",
                "handler": "scoped_operation_handler",
                "decision": "allow",
                "reason": "Allowed",
                "message_text": "gerar etiquetas",
            },
        ]
    )

    assert ConfirmationContinuationResolver(engine).resolve(event()) is None


def test_database_failure_is_fail_safe():
    engine = MagicMock()
    engine.begin.side_effect = RuntimeError("database unavailable")

    assert ConfirmationContinuationResolver(engine).resolve(event()) is None
