from app.googlechat.schemas import NormalizedChatEvent
from app.handlers.openclaw_agent_hook import (
    _build_owner_escalation_message,
    _rules_for_space,
    _should_deliver_in_thread,
    should_escalate_to_owner,
)
from app.handlers.openclaw_forward import _build_forward_payload
from app.policies.engine import PolicyDecision
from app.policies.intents import Intent


def test_clear_blocked_execution_does_not_escalate_to_owner():
    decision = PolicyDecision(
        policy_key="mkt_performance_analysis_only",
        intent=Intent.BUDGET_CHANGE,
        decision="deny",
        handler="deny_handler",
        reason="Operational execution is blocked in Mkt Performance group",
        scope="marketing_performance_analysis_only",
    )

    assert should_escalate_to_owner(decision) is False


def test_unknown_space_escalation_message_includes_context():
    event = NormalizedChatEvent(
        event_type="MESSAGE",
        space_name="spaces/UNKNOWN",
        space_display_name="Grupo Teste",
        user_name="users/123",
        user_display_name="João Victor",
        user_email="joao@example.com",
        thread_name="spaces/UNKNOWN/threads/t1",
        message_name="spaces/UNKNOWN/messages/m1",
        text="faz um relatório de certificados",
        raw={},
    )
    decision = PolicyDecision(
        policy_key="unknown_space",
        intent=Intent.PERFORMANCE_REPORT,
        decision="deny",
        handler="deny_handler",
        reason="Space is not configured in Lyra Chat Router",
        scope="unknown",
    )

    message = _build_owner_escalation_message(event, decision)

    assert should_escalate_to_owner(decision) is True
    assert "Grupo/space: Grupo Teste" in message
    assert "Solicitante: João Victor" in message
    assert "User ID: users/123" in message
    assert "Mensagem original:\nfaz um relatório de certificados" in message


def test_education_operations_requires_root_delivery():
    decision = PolicyDecision(
        policy_key="education_operations",
        intent=Intent.CORREIOS_LABEL,
        decision="allow",
        handler="scoped_operation_handler",
        reason="Allowed",
        scope="education_operations_analytics",
        continuation=True,
    )

    assert _should_deliver_in_thread(decision) is False
    assert "Never pass replyTo or threadId" in _rules_for_space(
        NormalizedChatEvent(
            event_type="MESSAGE",
            space_name="spaces/AAQAqhVlskk",
            space_display_name="Comitê - Operações Educacionais",
            user_name="users/102836791593473492239",
            user_display_name="Daiane",
            user_email=None,
            thread_name="spaces/AAQAqhVlskk/threads/labels",
            message_name="spaces/AAQAqhVlskk/messages/confirmation",
            text="@Lyra Sim",
            raw={},
        ),
        decision,
    )


def test_forward_payload_marks_root_only_and_continuation():
    event = NormalizedChatEvent(
        event_type="MESSAGE",
        space_name="spaces/AAQAqhVlskk",
        space_display_name="Comitê - Operações Educacionais",
        user_name="users/102836791593473492239",
        user_display_name="Daiane",
        user_email=None,
        thread_name="spaces/AAQAqhVlskk/threads/labels",
        message_name="spaces/AAQAqhVlskk/messages/confirmation",
        text="@Lyra Sim",
        raw={},
    )
    decision = PolicyDecision(
        policy_key="education_operations",
        intent=Intent.CORREIOS_LABEL,
        decision="allow",
        handler="scoped_operation_handler",
        reason="Allowed",
        scope="education_operations_analytics",
        continuation=True,
    )

    forwarded = _build_forward_payload(
        {"message": {"thread": {"name": event.thread_name}, "text": event.text}},
        event,
        decision,
    )

    assert forwarded["_lyraRouter"]["reply_mode"] == "root_only"
    assert forwarded["_lyraRouter"]["continuation"] is True
    assert forwarded["_lyraRouter"]["thread"] is None
    assert "thread" not in forwarded["message"]


def test_forward_payload_removes_workspace_addon_thread_context():
    event = NormalizedChatEvent(
        event_type="MESSAGE",
        space_name="spaces/AAQAqhVlskk",
        space_display_name="Comitê - Operações Educacionais",
        user_name="users/102836791593473492239",
        user_display_name="Daiane",
        user_email=None,
        thread_name="spaces/AAQAqhVlskk/threads/labels",
        message_name="spaces/AAQAqhVlskk/messages/confirmation",
        text="@Lyra Sim",
        raw={},
    )
    decision = PolicyDecision(
        policy_key="education_operations",
        intent=Intent.CORREIOS_LABEL,
        decision="allow",
        handler="scoped_operation_handler",
        reason="Allowed",
        scope="education_operations_analytics",
    )
    payload = {
        "chat": {
            "messagePayload": {
                "message": {
                    "text": event.text,
                    "thread": {"name": event.thread_name},
                }
            }
        }
    }

    forwarded = _build_forward_payload(payload, event, decision)

    assert "thread" not in forwarded["chat"]["messagePayload"]["message"]
