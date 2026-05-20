import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_googlechat_post_allows_analysis_in_dev_mode():
    client = TestClient(app)
    payload = json.loads(Path("tests/fixtures/googlechat_message.json").read_text())

    response = client.post("/googlechat/", json=payload)

    assert response.status_code == 200
    assert "Análise registrada" in response.json()["text"]


def test_googlechat_post_denies_operational_change_in_dev_mode():
    client = TestClient(app)
    payload = json.loads(Path("tests/fixtures/googlechat_message.json").read_text())
    payload["message"]["text"] = "Aumenta orçamento da campanha X"

    response = client.post("/googlechat/", json=payload)

    assert response.status_code == 200
    assert "fora do escopo permitido" in response.json()["text"]
    assert "Vou verificar com o Vinícios" in response.json()["text"]


def test_googlechat_post_allows_owner_dm_space_in_dev_mode():
    client = TestClient(app)
    payload = json.loads(Path("tests/fixtures/googlechat_message.json").read_text())
    payload["space"]["name"] = "spaces/mqWtpSAAAAE"
    payload["message"]["name"] = "spaces/mqWtpSAAAAE/messages/test"
    payload["message"]["thread"]["name"] = "spaces/mqWtpSAAAAE/threads/test"
    payload["message"]["text"] = "me ajuda"

    response = client.post("/googlechat/", json=payload)

    assert response.status_code == 200
    assert "Mensagem recebida" in response.json()["text"]


def test_googlechat_post_scoped_turnstile_response_in_dev_mode():
    client = TestClient(app)
    payload = json.loads(Path("tests/fixtures/googlechat_message.json").read_text())
    payload["space"]["name"] = "spaces/AAQAPj4LoCM"
    payload["message"]["name"] = "spaces/AAQAPj4LoCM/messages/test"
    payload["message"]["thread"]["name"] = "spaces/AAQAPj4LoCM/threads/test"
    payload["message"]["text"] = "libera entrada da catraca"

    response = client.post("/googlechat/", json=payload)

    assert response.status_code == 200
    assert "Pedido de catraca reconhecido" in response.json()["text"]


def test_googlechat_post_scoped_group_denies_out_of_scope_in_dev_mode():
    client = TestClient(app)
    payload = json.loads(Path("tests/fixtures/googlechat_message.json").read_text())
    payload["space"]["name"] = "spaces/AAQAqhVlskk"
    payload["message"]["name"] = "spaces/AAQAqhVlskk/messages/test"
    payload["message"]["thread"]["name"] = "spaces/AAQAqhVlskk/threads/test"
    payload["message"]["text"] = "bom dia"

    response = client.post("/googlechat/", json=payload)

    assert response.status_code == 200
    assert "fora do escopo permitido" in response.json()["text"]
    assert "Vou verificar com o Vinícios" in response.json()["text"]
