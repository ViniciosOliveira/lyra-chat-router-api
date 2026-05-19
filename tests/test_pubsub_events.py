import base64
import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.handlers import openclaw_agent_hook
from app.main import app


def _workspace_event(text: str = "Analisa o CPL", sender_type: str = "HUMAN") -> dict:
    return {
        "type": "google.workspace.chat.message.v1.created",
        "data": {
            "message": {
                "name": "spaces/AAQAiP4nKa4/messages/test-pubsub",
                "sender": {
                    "name": "users/108616006099141003473",
                    "type": sender_type,
                    "displayName": "Vinícios Oliveira",
                },
                "text": text,
                "argumentText": text,
                "thread": {"name": "spaces/AAQAiP4nKa4/threads/test"},
                "space": {"name": "spaces/AAQAiP4nKa4", "displayName": "Comitê de Mkt Performance"},
            }
        },
    }


def _pubsub_payload(event: dict) -> dict:
    data = base64.b64encode(json.dumps(event).encode("utf-8")).decode("ascii")
    return {"message": {"data": data, "messageId": "pubsub-1"}, "subscription": "sub"}


def _set_pubsub_env(monkeypatch, *, hook_enabled: bool = False):
    get_settings.cache_clear()
    monkeypatch.setenv("GOOGLE_CHAT_PUBSUB_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_CHAT_BOT_USER", "users/bot")
    monkeypatch.setenv("OPENCLAW_AGENT_HOOK_ENABLED", "true" if hook_enabled else "false")


def test_pubsub_endpoint_requires_shared_secret_in_dev(monkeypatch):
    _set_pubsub_env(monkeypatch)
    client = TestClient(app)

    response = client.post("/googlechat/events/pubsub", json=_pubsub_payload(_workspace_event()))

    get_settings.cache_clear()
    assert response.status_code == 401


def test_pubsub_endpoint_accepts_workspace_message_without_openclaw_hook(monkeypatch):
    _set_pubsub_env(monkeypatch)
    client = TestClient(app)

    response = client.post(
        "/googlechat/events/pubsub",
        json=_pubsub_payload(_workspace_event()),
        headers={"X-Lyra-Router-Secret": "test-secret"},
    )

    get_settings.cache_clear()
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert response.json()["handler"] == "pubsub_noop"


def test_pubsub_endpoint_accepts_query_secret_for_google_pubsub_push(monkeypatch):
    _set_pubsub_env(monkeypatch)
    client = TestClient(app)

    response = client.post(
        "/googlechat/events/pubsub?secret=test-secret",
        json=_pubsub_payload(_workspace_event()),
    )

    get_settings.cache_clear()
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_pubsub_endpoint_ignores_bot_messages(monkeypatch):
    _set_pubsub_env(monkeypatch)
    client = TestClient(app)

    response = client.post(
        "/googlechat/events/pubsub",
        json=_pubsub_payload(_workspace_event(sender_type="BOT")),
        headers={"X-Lyra-Router-Secret": "test-secret"},
    )

    get_settings.cache_clear()
    assert response.status_code == 200
    assert response.json()["reason"] == "bot_message"


def test_pubsub_endpoint_enqueues_openclaw_agent_hook(monkeypatch):
    async def fake_enqueue_openclaw_agent_turn(**kwargs):
        assert kwargs["event"].space_name == "spaces/AAQAiP4nKa4"
        assert kwargs["event"].text == "Analisa o CPL"
        assert kwargs["decision"].decision == "allow"
        return {"ok": True}

    _set_pubsub_env(monkeypatch, hook_enabled=True)
    monkeypatch.setattr(openclaw_agent_hook, "enqueue_openclaw_agent_turn", fake_enqueue_openclaw_agent_turn)
    # router imported the function directly, patch that binding too
    import app.pubsub.router as pubsub_router

    monkeypatch.setattr(pubsub_router, "enqueue_openclaw_agent_turn", fake_enqueue_openclaw_agent_turn)
    client = TestClient(app)

    response = client.post(
        "/googlechat/events/pubsub",
        json=_pubsub_payload(_workspace_event()),
        headers={"X-Lyra-Router-Secret": "test-secret"},
    )

    get_settings.cache_clear()
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
