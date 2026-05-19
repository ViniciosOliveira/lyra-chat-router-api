from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text

from app.admin.auth import verify_admin_secret
from app.db.session import get_engine
from app.googlechat.normalizer import normalize_event
from app.policies.engine import PolicyEngine

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(verify_admin_secret)],
)


def _no_database_response(kind: str) -> dict[str, Any]:
    return {"mode": "no_database", kind: []}


@router.get("/spaces")
def list_spaces() -> dict[str, Any]:
    engine = get_engine()
    if engine is None:
        return _no_database_response("spaces")

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                    s.space_name,
                    s.display_name,
                    s.space_type,
                    s.status,
                    p.key AS policy_key,
                    s.created_at,
                    s.updated_at
                FROM spaces s
                LEFT JOIN policies p ON p.id = s.default_policy_id
                ORDER BY s.updated_at DESC
                LIMIT 200
                """
            )
        ).mappings().all()

    return {"mode": "database", "spaces": [dict(row) for row in rows]}


@router.get("/routing-events")
def list_routing_events(limit: int = 50) -> dict[str, Any]:
    safe_limit = max(1, min(limit, 200))
    engine = get_engine()
    if engine is None:
        return _no_database_response("routing_events")

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                    re.created_at,
                    re.classified_intent,
                    re.handler,
                    re.decision,
                    re.reason,
                    re.latency_ms,
                    m.provider_message_id,
                    m.thread_name,
                    m.text,
                    s.space_name,
                    u.google_user_name
                FROM routing_events re
                LEFT JOIN messages m ON m.id = re.message_id
                LEFT JOIN spaces s ON s.id = m.space_id
                LEFT JOIN users u ON u.id = m.user_id
                ORDER BY re.created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": safe_limit},
        ).mappings().all()

    return {"mode": "database", "routing_events": [dict(row) for row in rows]}


@router.post("/test/route")
async def test_route(request: Request) -> dict[str, Any]:
    payload = await request.json()
    event = normalize_event(payload)
    decision = PolicyEngine().decide(event)

    return {
        "event": {
            "event_type": event.event_type,
            "space_name": event.space_name,
            "user_name": event.user_name,
            "thread_name": event.thread_name,
            "message_name": event.message_name,
            "text": event.text,
        },
        "decision": {
            "policy_key": decision.policy_key,
            "intent": decision.intent.value,
            "decision": decision.decision,
            "handler": decision.handler,
            "reason": decision.reason,
        },
    }
