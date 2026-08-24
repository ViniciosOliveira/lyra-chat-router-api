from app.core.config import get_settings
from app.googlechat.schemas import NormalizedChatEvent
from app.handlers.openclaw_agent_hook import (
    _build_agent_message,
    _build_owner_escalation_message,
    _post_agent_hook,
    _post_forward_fallback_hook,
    _rules_for_space,
    _should_deliver_in_thread,
    _timeout_seconds_for_space,
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


def test_shared_dev_space_uses_independent_product_rules():
    event = NormalizedChatEvent(
        event_type="MESSAGE",
        space_name="spaces/AAQA8PyOLEI",
        space_display_name="Dev - Shared",
        user_name="users/108616006099141003473",
        user_display_name="Vinícios Oliveira",
        user_email="vinicios@grupooliveirarocha.com",
        thread_name="spaces/AAQA8PyOLEI/threads/test",
        message_name="spaces/AAQA8PyOLEI/messages/test",
        text="pode seguir",
        raw={},
    )
    decision = PolicyDecision(
        policy_key="shared_dev_group",
        intent=Intent.UNKNOWN,
        decision="allow",
        handler="openclaw_agent_hook",
        reason="Dev owner allowed",
        scope="shared_dev_owner_only",
    )

    rules = _rules_for_space(event, decision)

    assert "autonomous Shared application platform" in rules
    assert "memory/projects/shared/README.md" in rules
    assert "Do not implement Shared runtime behavior inside Mission Control" in rules
    assert "durable external checkpoints for long execution" in rules
    assert "Do not create, approve, dispatch or verify a Lyra OS demand" in rules
    assert "independent external journal" in rules
    assert "control plane only" in rules
    assert "Never block the group turn with sleep, long waits or polling loops" in rules

    message = _build_agent_message(event, decision)
    assert "external execution owns implementation, tests, CI and verification" in message
    assert "external journal and execution are both active and traceable" in message


def test_all_dev_scopes_use_external_fast_lane_without_lyra_os_dependency():
    event = NormalizedChatEvent(
        event_type="MESSAGE",
        space_name="spaces/mqWtpSAAAAE",
        space_display_name="Comitê - Desenvolvimento",
        user_name="users/108616006099141003473",
        user_display_name="Vinícios Oliveira",
        user_email="vinicios@grupooliveirarocha.com",
        thread_name=None,
        message_name="spaces/mqWtpSAAAAE/messages/test",
        text="implemente",
        raw={},
    )
    for scope in (
        "crm_dev_owner_only",
        "mission_control_dev_owner_only",
        "edune_v2_dev_owner_only",
        "fesn_dev_owner_only",
        "shared_dev_owner_only",
        "lyra_os_product_operations_owner_only",
        "general_owner_only",
    ):
        decision = PolicyDecision(
            policy_key="dev",
            intent=Intent.UNKNOWN,
            decision="allow",
            handler="openclaw_agent_hook",
            reason="owner allowed",
            scope=scope,
        )
        rules = _rules_for_space(event, decision)
        assert "external Google Chat fast lane" in rules
        assert "Do not create, approve, dispatch or verify a Lyra OS demand" in rules
        assert "Product deploys" in rules


def test_shared_dev_space_keeps_group_turn_timeout_short():
    settings = get_settings()
    decision = PolicyDecision(
        policy_key="shared_dev_group",
        intent=Intent.UNKNOWN,
        decision="allow",
        handler="openclaw_agent_hook",
        reason="Dev owner allowed",
        scope="shared_dev_owner_only",
    )

    assert _timeout_seconds_for_space(settings=settings, decision=decision) == (
        settings.openclaw_agent_hook_timeout_seconds
    )


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


def test_every_router_scope_requires_root_delivery():
    for scope in (
        "general_owner_only",
        "crm_dev_owner_only",
        "mission_control_dev_owner_only",
        "marketing_performance_analysis_only",
        "education_operations_analytics",
    ):
        decision = PolicyDecision(
            policy_key="test",
            intent=Intent.UNKNOWN,
            decision="allow",
            handler="openclaw_agent_hook",
            reason="Allowed",
            scope=scope,
        )

        assert _should_deliver_in_thread(decision) is False


def test_agent_hook_and_fallback_never_forward_thread_id(monkeypatch):
    settings = get_settings()
    event = NormalizedChatEvent(
        event_type="MESSAGE",
        space_name="spaces/mqWtpSAAAAE",
        space_display_name="Vinícios Oliveira",
        user_name="users/108616006099141003473",
        user_display_name="Vinícios Oliveira",
        user_email="vinicios@grupooliveirarocha.com",
        thread_name="spaces/mqWtpSAAAAE/threads/should-not-leak",
        message_name="spaces/mqWtpSAAAAE/messages/test",
        text="teste",
        raw={},
    )
    decision = PolicyDecision(
        policy_key="owner_dm",
        intent=Intent.UNKNOWN,
        decision="allow",
        handler="openclaw_agent_hook",
        reason="Owner allowed",
        scope="general_owner_only",
    )
    captured = []

    def fake_post(*, settings, payload):
        captured.append(payload)
        return {"ok": True}

    monkeypatch.setattr(
        "app.handlers.openclaw_agent_hook._post_agent_hook_payload",
        fake_post,
    )

    _post_agent_hook(settings=settings, event=event, decision=decision)
    _post_forward_fallback_hook(settings=settings, event=event, decision=decision)

    assert len(captured) == 2
    assert all("threadId" not in payload for payload in captured)
    assert all("Thread: suppressed for root-only delivery" in payload["message"] for payload in captured)


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


def test_forward_payload_removes_thread_context_for_owner_dm_too():
    event = NormalizedChatEvent(
        event_type="MESSAGE",
        space_name="spaces/mqWtpSAAAAE",
        space_display_name="Vinícios Oliveira",
        user_name="users/108616006099141003473",
        user_display_name="Vinícios Oliveira",
        user_email="vinicios@grupooliveirarocha.com",
        thread_name="spaces/mqWtpSAAAAE/threads/should-not-leak",
        message_name="spaces/mqWtpSAAAAE/messages/test",
        text="teste",
        raw={},
    )
    decision = PolicyDecision(
        policy_key="owner_dm",
        intent=Intent.UNKNOWN,
        decision="allow",
        handler="openclaw_forward",
        reason="Owner allowed",
        scope="general_owner_only",
    )
    original = {
        "message": {
            "text": event.text,
            "thread": {"name": event.thread_name},
        }
    }

    forwarded = _build_forward_payload(original, event, decision)

    assert "thread" in original["message"]
    assert "thread" not in forwarded["message"]
    assert forwarded["_lyraRouter"]["thread"] is None
    assert forwarded["_lyraRouter"]["reply_mode"] == "root_only"
