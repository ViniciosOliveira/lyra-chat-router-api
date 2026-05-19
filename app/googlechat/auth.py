import base64
import json
import logging

from fastapi import Header, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import Settings

logger = logging.getLogger(__name__)

GOOGLE_CHAT_SYSTEM_ACCOUNT = "chat@system.gserviceaccount.com"
GOOGLE_CHAT_ADDONS_ACCOUNT_SUFFIX = "@gcp-sa-gsuiteaddons.iam.gserviceaccount.com"


def _candidate_audiences(configured_audience: str) -> list[str]:
    audiences = [configured_audience]
    if configured_audience.endswith("/"):
        audiences.append(configured_audience.rstrip("/"))
    else:
        audiences.append(f"{configured_audience}/")
    return list(dict.fromkeys(audiences))


def _is_allowed_google_chat_principal(email: str | None) -> bool:
    if not email:
        return True
    return email == GOOGLE_CHAT_SYSTEM_ACCOUNT or email.endswith(GOOGLE_CHAT_ADDONS_ACCOUNT_SUFFIX)


def _decode_unverified_claims(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")))
    except Exception:
        return {}


async def verify_google_chat_authorization(
    settings: Settings,
    authorization: str | None = Header(default=None),
) -> dict:
    if settings.google_chat_dev_bypass_auth and not settings.is_prod:
        return {"mode": "dev_bypass"}

    if not authorization or not authorization.lower().startswith("bearer "):
        logger.warning(
            "google_chat_auth_missing audience=%s auth_present=%s",
            settings.google_chat_audience,
            bool(authorization),
        )
        raise HTTPException(status_code=401, detail="Missing Google Chat bearer token")

    token = authorization.split(" ", 1)[1].strip()
    unverified_claims = _decode_unverified_claims(token)
    last_error: Exception | None = None

    for audience in _candidate_audiences(settings.google_chat_audience):
        try:
            claims = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                audience=audience,
            )
            break
        except Exception as exc:  # pragma: no cover - depends on external Google certs/token
            last_error = exc
    else:
        logger.warning(
            "google_chat_auth_invalid expected_audiences=%s token_aud=%s token_iss=%s token_email=%s error=%s",
            _candidate_audiences(settings.google_chat_audience),
            unverified_claims.get("aud"),
            unverified_claims.get("iss"),
            unverified_claims.get("email"),
            last_error.__class__.__name__ if last_error else None,
        )
        raise HTTPException(status_code=401, detail="Invalid Google Chat bearer token") from last_error

    email = claims.get("email")
    if not _is_allowed_google_chat_principal(email):
        # Add-on/app-principal modes can be supported deliberately later.
        logger.warning(
            "google_chat_auth_unexpected_principal token_aud=%s token_iss=%s token_email=%s",
            claims.get("aud"),
            claims.get("iss"),
            email,
        )
        raise HTTPException(status_code=401, detail="Unexpected Google Chat token principal")

    return claims
