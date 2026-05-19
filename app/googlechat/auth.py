from fastapi import Header, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import Settings


async def verify_google_chat_authorization(
    settings: Settings,
    authorization: str | None = Header(default=None),
) -> dict:
    if settings.google_chat_dev_bypass_auth and not settings.is_prod:
        return {"mode": "dev_bypass"}

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Google Chat bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=settings.google_chat_audience,
        )
    except Exception as exc:  # pragma: no cover - depends on external Google certs/token
        raise HTTPException(status_code=401, detail="Invalid Google Chat bearer token") from exc

    email = claims.get("email")
    if email and email != "chat@system.gserviceaccount.com":
        # Add-on/app-principal modes can be supported deliberately later.
        raise HTTPException(status_code=401, detail="Unexpected Google Chat token principal")

    return claims
