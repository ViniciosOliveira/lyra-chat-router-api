from fastapi.testclient import TestClient

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
