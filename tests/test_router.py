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
    assert "só posso fazer análises" in response.json()["text"]
