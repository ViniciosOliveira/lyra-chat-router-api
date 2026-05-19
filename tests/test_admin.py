import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ADMIN_HEADERS = {"X-MC-Admin-Secret": "dev-admin-secret"}


def test_admin_requires_secret():
    client = TestClient(app)

    response = client.get("/admin/spaces")

    assert response.status_code == 401


def test_admin_rejects_invalid_secret():
    client = TestClient(app)

    response = client.get("/admin/spaces", headers={"X-MC-Admin-Secret": "wrong"})

    assert response.status_code == 403


def test_admin_spaces_without_database_returns_empty_safe_payload():
    client = TestClient(app)

    response = client.get("/admin/spaces", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json() == {"mode": "no_database", "spaces": []}


def test_admin_routing_events_without_database_returns_empty_safe_payload():
    client = TestClient(app)

    response = client.get("/admin/routing-events", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json() == {"mode": "no_database", "routing_events": []}


def test_admin_test_route_allows_analysis():
    client = TestClient(app)
    payload = json.loads(Path("tests/fixtures/googlechat_message.json").read_text())

    response = client.post("/admin/test/route", json=payload, headers=ADMIN_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["event"]["space_name"] == "spaces/AAQAiP4nKa4"
    assert body["decision"]["decision"] == "allow"
    assert body["decision"]["handler"] == "analytics_handler"


def test_admin_test_route_blocks_operational_change():
    client = TestClient(app)
    payload = json.loads(Path("tests/fixtures/googlechat_message.json").read_text())
    payload["message"]["text"] = "Faz deploy da tag no site"

    response = client.post("/admin/test/route", json=payload, headers=ADMIN_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["decision"]["decision"] == "deny"
    assert body["decision"]["handler"] == "deny_handler"
