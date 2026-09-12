import json
from pathlib import Path

from app.main import app
from tests.asgi_client import ASGITestClient as TestClient


def test_googlechat_post_accepts_no_trailing_slash_in_dev_mode():
    client = TestClient(app)
    payload = json.loads(Path("tests/fixtures/googlechat_message.json").read_text())

    response = client.post("/googlechat", json=payload, follow_redirects=False)

    assert response.status_code == 200
    assert "Análise registrada" in response.json()["text"]
