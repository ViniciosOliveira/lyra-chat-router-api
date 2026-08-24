import asyncio
import base64
import json
import logging
import re
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from fastapi import Header, HTTPException
from google.auth import exceptions as google_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import Settings

logger = logging.getLogger(__name__)

GOOGLE_CHAT_SYSTEM_ACCOUNT = "chat@system.gserviceaccount.com"
GOOGLE_CHAT_ADDONS_ACCOUNT_SUFFIX = "@gcp-sa-gsuiteaddons.iam.gserviceaccount.com"
GOOGLE_CERTS_REQUEST_TIMEOUT_SECONDS = 3.0
GOOGLE_CERTS_CACHE_FALLBACK_TTL_SECONDS = 300.0
GOOGLE_CERTS_CACHE_MAX_TTL_SECONDS = 3600.0
GOOGLE_CERTS_RETRY_DELAYS_SECONDS = (0.15, 0.35)


@dataclass(frozen=True)
class _CachedGoogleResponse:
    status: int
    data: bytes
    headers: Mapping[str, str]


class _CachedGoogleCertsRequest:
    """Cache successful Google certificate responses in memory per worker."""

    def __init__(
        self,
        delegate: Callable | None = None,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._delegate = delegate or google_requests.Request()
        self._now = now
        self._cache: dict[str, tuple[float, _CachedGoogleResponse]] = {}
        self._lock = threading.Lock()

    def __call__(
        self,
        url: str,
        method: str = "GET",
        body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float = GOOGLE_CERTS_REQUEST_TIMEOUT_SECONDS,
        **kwargs,
    ):
        if method.upper() != "GET":
            return self._delegate(
                url,
                method=method,
                body=body,
                headers=headers,
                timeout=timeout,
                **kwargs,
            )

        with self._lock:
            cached = self._cache.get(url)
            now = self._now()
            if cached and cached[0] > now:
                return cached[1]

            response = self._delegate(
                url,
                method=method,
                body=body,
                headers=headers,
                timeout=timeout,
                **kwargs,
            )
            if response.status == 200:
                snapshot = _CachedGoogleResponse(
                    status=response.status,
                    data=bytes(response.data),
                    headers=dict(response.headers),
                )
                self._cache[url] = (now + _cache_ttl_seconds(response.headers), snapshot)
                return snapshot
            return response


def _cache_ttl_seconds(headers: Mapping[str, str]) -> float:
    cache_control = next(
        (value for key, value in headers.items() if key.lower() == "cache-control"),
        "",
    )
    match = re.search(r"(?:^|,)\s*max-age\s*=\s*(\d+)", cache_control, re.IGNORECASE)
    if not match:
        return GOOGLE_CERTS_CACHE_FALLBACK_TTL_SECONDS
    return min(float(match.group(1)), GOOGLE_CERTS_CACHE_MAX_TTL_SECONDS)


_GOOGLE_CERTS_REQUEST = _CachedGoogleCertsRequest()


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


async def _verify_oauth2_token_with_retry(token: str, audience: str) -> dict:
    attempts = len(GOOGLE_CERTS_RETRY_DELAYS_SECONDS) + 1
    for attempt in range(attempts):
        try:
            return id_token.verify_oauth2_token(
                token,
                _GOOGLE_CERTS_REQUEST,
                audience=audience,
            )
        except google_exceptions.TransportError as exc:
            if attempt == attempts - 1:
                raise
            logger.warning(
                "google_chat_auth_certs_retry audience=%s attempt=%s error=%s",
                audience,
                attempt + 1,
                exc.__class__.__name__,
            )
            await asyncio.sleep(GOOGLE_CERTS_RETRY_DELAYS_SECONDS[attempt])

    raise RuntimeError("unreachable Google certificate retry state")


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
    claims: dict | None = None

    for audience in _candidate_audiences(settings.google_chat_audience):
        try:
            claims = await _verify_oauth2_token_with_retry(token, audience)
            break
        except google_exceptions.TransportError as exc:
            last_error = exc
            break
        except Exception as exc:  # pragma: no cover - depends on external Google certs/token
            last_error = exc

    if claims is None:
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
