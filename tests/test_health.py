from app.main import app
from tests.asgi_client import ASGITestClient as TestClient


def test_healthcheck():
    client = TestClient(app)
    response = client.get("/googlechat/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
