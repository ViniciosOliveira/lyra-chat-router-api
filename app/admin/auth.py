import secrets

from fastapi import Depends, Header, HTTPException

from app.core.config import Settings, get_settings


async def verify_admin_secret(
    x_mc_admin_secret: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    expected_secret = settings.effective_mc_admin_secret

    if settings.is_prod and not settings.mc_admin_shared_secret:
        raise HTTPException(status_code=503, detail="Admin secret is not configured")

    if not x_mc_admin_secret:
        raise HTTPException(status_code=401, detail="Missing admin secret")

    if not secrets.compare_digest(x_mc_admin_secret, expected_secret):
        raise HTTPException(status_code=403, detail="Invalid admin secret")
