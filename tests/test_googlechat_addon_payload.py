from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.delivery.ledger import DeliveryState
from app.googlechat import router as googlechat_router
from app.handlers import openclaw_agent_hook, openclaw_forward
from app.main import app


def _addon_payload(text: str = "oi") -> dict:
    return {
        "chat": {
            "user": {
                "name": "users/108616006099141003473",
                "email": "vinicios@grupooliveirarocha.com",
                "displayName": "Vinícios Oliveira",
            },
            "messagePayload": {
                "space": {
                    "name": "spaces/mqWtpSAAAAE",
                    "type": "DM",
                    "spaceType": "DIRECT_MESSAGE",
                },
                "message": {
                    "name": "spaces/mqWtpSAAAAE/messages/test",
                    "text": text,
                    "space": {"name": "spaces/mqWtpSAAAAE", "type": "DM"},
                    "sender": {
                        "name": "users/108616006099141003473",
                        "email": "vinicios@grupooliveirarocha.com",
                        "displayName": "Vinícios Oliveira",
                    },
                    "thread": {"name": "spaces/mqWtpSAAAAE/threads/test"},
                    "argumentText": text,
                    "formattedText": text,
                },
            },
        },
        "commonEventObject": {"hostApp": "CHAT"},
    }


def test_workspace_addon_message_payload_uses_create_message_action_envelope():
    client = TestClient(app)

    response = client.post("/googlechat", json=_addon_payload())

    assert response.status_code == 200
    body = response.json()
    message = body["hostAppDataAction"]["chatDataAction"]["createMessageAction"]["message"]
    assert "Mensagem recebida" in message["text"]


def test_workspace_addon_message_payload_normalizes_message_fields():
    client = TestClient(app)

    response = client.post("/googlechat", json=_addon_payload("Analisa o CPL"))

    assert response.status_code == 200
    message = response.json()["hostAppDataAction"]["chatDataAction"]["createMessageAction"]["message"]
    assert "Mensagem recebida" in message["text"]


def test_workspace_addon_message_payload_forwards_to_openclaw_when_enabled(monkeypatch):
    async def fake_forward_to_openclaw(**kwargs):
        assert kwargs["settings"].openclaw_forward_enabled is True
        assert kwargs["event"].space_name == "spaces/mqWtpSAAAAE"
        assert kwargs["event"].text == "oi Lyra"
        assert kwargs["decision"].decision == "allow"
        return {"text": "Resposta real da Lyra"}

    monkeypatch.setattr(googlechat_router, "forward_to_openclaw", fake_forward_to_openclaw)

    get_settings.cache_clear()
    monkeypatch.setenv("OPENCLAW_FORWARD_ENABLED", "true")
    monkeypatch.setenv("OPENCLAW_FORWARD_URL", "http://10.0.0.5:18789/googlechat")

    client = TestClient(app)
    response = client.post("/googlechat", json=_addon_payload("oi Lyra"))

    get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["text"] == "Resposta real da Lyra"


def test_workspace_addon_message_payload_skips_completed_duplicate(monkeypatch):
    class FakeDeliveryLedger:
        def record_received(self, event):
            assert event.message_name == "spaces/mqWtpSAAAAE/messages/test"
            return DeliveryState(
                mode="database",
                provider_message_id=event.message_name,
                status="delivered",
                stage="googlechat_sync_response",
                duplicate_count=1,
            )

        def mark_delivered(self, *args, **kwargs):
            raise AssertionError("completed duplicate must not be delivered again")

    async def fake_forward_to_openclaw(**kwargs):
        raise AssertionError("completed duplicate must not be forwarded again")

    monkeypatch.setattr(googlechat_router, "DeliveryLedger", FakeDeliveryLedger)
    monkeypatch.setattr(googlechat_router, "forward_to_openclaw", fake_forward_to_openclaw)

    get_settings.cache_clear()
    monkeypatch.setenv("OPENCLAW_FORWARD_ENABLED", "true")
    monkeypatch.setenv("OPENCLAW_FORWARD_URL", "http://10.0.0.5:18789/googlechat")

    client = TestClient(app)
    response = client.post("/googlechat", json=_addon_payload("oi Lyra"))

    get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json() == {}


def test_workspace_addon_message_payload_returns_empty_ok_when_openclaw_forward_fails(monkeypatch):
    async def fake_forward_to_openclaw(**kwargs):
        raise openclaw_forward.OpenClawForwardError("boom")

    monkeypatch.setattr(googlechat_router, "forward_to_openclaw", fake_forward_to_openclaw)

    get_settings.cache_clear()
    monkeypatch.setenv("OPENCLAW_FORWARD_ENABLED", "true")
    monkeypatch.setenv("OPENCLAW_FORWARD_URL", "http://10.0.0.5:18789/googlechat")

    client = TestClient(app)
    response = client.post("/googlechat", json=_addon_payload("oi Lyra"))

    get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json() == {}


def test_workspace_addon_message_payload_enqueues_fallback_when_forward_fails(monkeypatch):
    async def fake_forward_to_openclaw(**kwargs):
        raise openclaw_forward.OpenClawForwardError("boom")

    async def fake_enqueue_openclaw_forward_fallback(**kwargs):
        assert kwargs["event"].space_name == "spaces/mqWtpSAAAAE"
        assert kwargs["event"].text == "oi Lyra"
        return {"status": "queued"}

    monkeypatch.setattr(googlechat_router, "forward_to_openclaw", fake_forward_to_openclaw)
    monkeypatch.setattr(
        googlechat_router,
        "enqueue_openclaw_forward_fallback",
        fake_enqueue_openclaw_forward_fallback,
    )

    get_settings.cache_clear()
    monkeypatch.setenv("OPENCLAW_FORWARD_ENABLED", "true")
    monkeypatch.setenv("OPENCLAW_FORWARD_URL", "http://10.0.0.5:18789/googlechat")
    monkeypatch.setenv("OPENCLAW_AGENT_HOOK_ENABLED", "true")
    monkeypatch.setenv("OPENCLAW_AGENT_HOOK_URL", "http://10.0.0.5:18789/hooks/agent")
    monkeypatch.setenv("OPENCLAW_AGENT_HOOK_TOKEN", "test-token")

    client = TestClient(app)
    response = client.post("/googlechat", json=_addon_payload("oi Lyra"))

    get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json() == {}


def test_workspace_addon_message_payload_returns_empty_ok_when_openclaw_returns_empty_response(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = "{}"

        @staticmethod
        def json():
            return {}

    def fake_post(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr(openclaw_forward.requests, "post", fake_post)

    get_settings.cache_clear()
    monkeypatch.setenv("OPENCLAW_FORWARD_ENABLED", "true")
    monkeypatch.setenv("OPENCLAW_FORWARD_URL", "http://10.0.0.5:18789/googlechat")

    client = TestClient(app)
    response = client.post("/googlechat", json=_addon_payload("oi Lyra"))

    get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json() == {}


def test_workspace_addon_message_payload_does_not_enqueue_fallback_when_openclaw_returns_empty_ok(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = "{}"

        @staticmethod
        def json():
            return {}

    def fake_post(*args, **kwargs):
        return FakeResponse()

    async def fake_enqueue_openclaw_forward_fallback(**kwargs):
        raise AssertionError("fallback must not run after a successful 2xx OpenClaw forward")

    monkeypatch.setattr(openclaw_forward.requests, "post", fake_post)
    monkeypatch.setattr(
        googlechat_router,
        "enqueue_openclaw_forward_fallback",
        fake_enqueue_openclaw_forward_fallback,
    )

    get_settings.cache_clear()
    monkeypatch.setenv("OPENCLAW_FORWARD_ENABLED", "true")
    monkeypatch.setenv("OPENCLAW_FORWARD_URL", "http://10.0.0.5:18789/googlechat")
    monkeypatch.setenv("OPENCLAW_AGENT_HOOK_ENABLED", "true")
    monkeypatch.setenv("OPENCLAW_AGENT_HOOK_URL", "http://10.0.0.5:18789/hooks/agent")
    monkeypatch.setenv("OPENCLAW_AGENT_HOOK_TOKEN", "test-token")

    client = TestClient(app)
    response = client.post("/googlechat", json=_addon_payload("oi Lyra"))

    get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json() == {}
