from app.googlechat.schemas import NormalizedChatEvent
from app.handlers.openclaw_agent_hook import _build_owner_escalation_message, should_escalate_to_owner
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
