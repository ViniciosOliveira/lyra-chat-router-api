import asyncio

import pytest
from google.auth import exceptions as google_exceptions

from app.googlechat import auth
from app.googlechat.auth import (
    _CachedGoogleCertsRequest,
    _cache_ttl_seconds,
    _candidate_audiences,
    _is_allowed_google_chat_principal,
)


class _Response:
    def __init__(self, *, status=200, data=b"{}", headers=None):
        self.status = status
        self.data = data
        self.headers = headers or {}


def test_candidate_audiences_accepts_trailing_slash_variants():
    assert _candidate_audiences("https://api.grupooliveirarocha.com/googlechat/") == [
        "https://api.grupooliveirarocha.com/googlechat/",
        "https://api.grupooliveirarocha.com/googlechat",
    ]

    assert _candidate_audiences("https://api.grupooliveirarocha.com/googlechat") == [
        "https://api.grupooliveirarocha.com/googlechat",
        "https://api.grupooliveirarocha.com/googlechat/",
    ]


def test_google_chat_principal_allows_chat_and_gsuiteaddons_accounts():
    assert _is_allowed_google_chat_principal("chat@system.gserviceaccount.com")
    assert _is_allowed_google_chat_principal(
        "service-112073849348@gcp-sa-gsuiteaddons.iam.gserviceaccount.com"
    )
    assert not _is_allowed_google_chat_principal("attacker@example.com")


def test_google_certs_request_reuses_successful_response_until_max_age():
    calls = []
    now = [100.0]

    def delegate(*args, **kwargs):
        calls.append((args, kwargs))
        return _Response(data=b'{"key": "certificate"}', headers={"Cache-Control": "max-age=60"})

    request = _CachedGoogleCertsRequest(delegate=delegate, now=lambda: now[0])

    first = request("https://www.googleapis.com/oauth2/v1/certs")
    second = request("https://www.googleapis.com/oauth2/v1/certs")

    assert first.data == second.data
    assert len(calls) == 1
    assert calls[0][1]["timeout"] == auth.GOOGLE_CERTS_REQUEST_TIMEOUT_SECONDS

    now[0] = 161.0
    request("https://www.googleapis.com/oauth2/v1/certs")
    assert len(calls) == 2


def test_google_certs_cache_ttl_uses_fallback_and_caps_server_value():
    assert _cache_ttl_seconds({}) == auth.GOOGLE_CERTS_CACHE_FALLBACK_TTL_SECONDS
    assert _cache_ttl_seconds({"cache-control": "public, max-age=120"}) == 120.0
    assert (
        _cache_ttl_seconds({"Cache-Control": "max-age=999999"})
        == auth.GOOGLE_CERTS_CACHE_MAX_TTL_SECONDS
    )


def test_google_token_verification_retries_only_transport_errors(monkeypatch):
    calls = []
    sleeps = []

    def verify(*args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) < 3:
            raise google_exceptions.TransportError("temporary cert fetch failure")
        return {"aud": kwargs["audience"], "iss": "accounts.google.com"}

    async def fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr(auth.id_token, "verify_oauth2_token", verify)
    monkeypatch.setattr(auth.asyncio, "sleep", fake_sleep)

    claims = asyncio.run(auth._verify_oauth2_token_with_retry("token", "audience"))

    assert claims["aud"] == "audience"
    assert len(calls) == 3
    assert sleeps == list(auth.GOOGLE_CERTS_RETRY_DELAYS_SECONDS)


def test_google_token_verification_does_not_retry_invalid_token(monkeypatch):
    calls = []

    def verify(*args, **kwargs):
        calls.append((args, kwargs))
        raise ValueError("invalid token")

    monkeypatch.setattr(auth.id_token, "verify_oauth2_token", verify)

    with pytest.raises(ValueError, match="invalid token"):
        asyncio.run(auth._verify_oauth2_token_with_retry("token", "audience"))

    assert len(calls) == 1


def test_google_chat_authorization_fails_closed_after_transport_retries(monkeypatch):
    calls = []

    def verify(*args, **kwargs):
        calls.append((args, kwargs))
        raise google_exceptions.TransportError("certificate endpoint unavailable")

    async def fake_sleep(_delay):
        return None

    monkeypatch.setattr(auth.id_token, "verify_oauth2_token", verify)
    monkeypatch.setattr(auth.asyncio, "sleep", fake_sleep)
    settings = auth.Settings(
        app_env="prod",
        google_chat_dev_bypass_auth=False,
        google_chat_audience="https://api.example.com/googlechat",
    )

    with pytest.raises(auth.HTTPException) as exc_info:
        asyncio.run(
            auth.verify_google_chat_authorization(
                settings=settings,
                authorization="Bearer invalid.token.value",
            )
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid Google Chat bearer token"
    assert len(calls) == 3
