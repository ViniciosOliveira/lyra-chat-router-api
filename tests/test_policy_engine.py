import json
from pathlib import Path

from app.googlechat.normalizer import normalize_event
from app.policies.engine import PolicyEngine


def event_with_text(text: str):
    payload = json.loads(Path("tests/fixtures/googlechat_message.json").read_text())
    payload["message"]["text"] = text
    return normalize_event(payload)


def test_allows_marketing_analysis():
    decision = PolicyEngine().decide(event_with_text("Analisa o CPL do Google Ads"))

    assert decision.decision == "allow"
    assert decision.handler == "analytics_handler"


def test_blocks_budget_change():
    decision = PolicyEngine().decide(event_with_text("Aumenta orçamento da campanha X"))

    assert decision.decision == "deny"
    assert decision.handler == "deny_handler"


def test_blocks_deploy():
    decision = PolicyEngine().decide(event_with_text("Faz deploy da tag no site"))

    assert decision.decision == "deny"
