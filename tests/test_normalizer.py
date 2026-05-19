import json
from pathlib import Path

from app.googlechat.normalizer import normalize_event


def test_normalize_googlechat_message_fixture():
    payload = json.loads(Path("tests/fixtures/googlechat_message.json").read_text())
    event = normalize_event(payload)

    assert event.event_type == "MESSAGE"
    assert event.space_name == "spaces/AAQAiP4nKa4"
    assert event.user_name == "users/108616006099141003473"
    assert event.text == "Analisa o CPL do Google Ads essa semana"
