import json
from pathlib import Path

from app.googlechat.normalizer import normalize_event
from app.policies.engine import PolicyEngine

OWNER = "users/108616006099141003473"


def event_with_text(text: str, space: str = "spaces/AAQAiP4nKa4", user: str = OWNER):
    payload = json.loads(Path("tests/fixtures/googlechat_message.json").read_text())
    payload["space"]["name"] = space
    payload["message"]["name"] = f"{space}/messages/test"
    payload["message"]["thread"]["name"] = f"{space}/threads/test"
    payload["user"]["name"] = user
    payload["message"]["text"] = text
    return normalize_event(payload)


def test_allows_marketing_analysis():
    decision = PolicyEngine().decide(event_with_text("Analisa o CPL do Google Ads"))

    assert decision.decision == "allow"
    assert decision.handler == "analytics_handler"
    assert decision.scope == "marketing_performance_analysis_only"


def test_blocks_budget_change():
    decision = PolicyEngine().decide(event_with_text("Aumenta orçamento da campanha X"))

    assert decision.decision == "deny"
    assert decision.handler == "deny_handler"


def test_blocks_deploy():
    decision = PolicyEngine().decide(event_with_text("Faz deploy da tag no site"))

    assert decision.decision == "deny"


def test_allows_owner_dm_space():
    decision = PolicyEngine().decide(event_with_text("me ajuda", space="spaces/mqWtpSAAAAE"))

    assert decision.decision == "allow"
    assert decision.policy_key == "owner_dm"
    assert decision.scope == "general_owner_only"


def test_blocks_unknown_space():
    decision = PolicyEngine().decide(event_with_text("me ajuda", space="spaces/UNKNOWN"))

    assert decision.decision == "deny"
    assert decision.policy_key == "unknown_space"


def test_blocks_unauthorized_user_in_known_space():
    decision = PolicyEngine().decide(
        event_with_text("me ajuda", space="spaces/mqWtpSAAAAE", user="users/unauthorized")
    )

    assert decision.decision == "deny"
    assert decision.reason == "User is not allowed for this Google Chat space"


def test_allows_turnstile_scope_in_turnstile_group():
    decision = PolicyEngine().decide(event_with_text("libera entrada da catraca", space="spaces/AAQAPj4LoCM"))

    assert decision.decision == "allow"
    assert decision.handler == "scoped_operation_handler"
    assert decision.scope == "turnstile_only"


def test_blocks_non_turnstile_scope_in_turnstile_group():
    decision = PolicyEngine().decide(event_with_text("faz relatório de marketing", space="spaces/AAQAPj4LoCM"))

    assert decision.decision == "deny"
    assert decision.scope == "turnstile_only"


def test_allows_certificate_scope():
    decision = PolicyEngine().decide(event_with_text("assinar certificado NR", space="spaces/AAQAqhVlskk"))

    assert decision.decision == "allow"
    assert decision.handler == "scoped_operation_handler"
    assert decision.scope == "certificates_correios_only"


def test_allows_correios_scope():
    decision = PolicyEngine().decide(event_with_text("gerar etiqueta correios", space="spaces/AAQAqhVlskk"))

    assert decision.decision == "allow"
    assert decision.handler == "scoped_operation_handler"
    assert decision.scope == "certificates_correios_only"
