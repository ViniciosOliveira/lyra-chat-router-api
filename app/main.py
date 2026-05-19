from fastapi import FastAPI

from app.admin.router import router as admin_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.googlechat.router import router as googlechat_router

configure_logging()
settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.include_router(googlechat_router)
app.include_router(admin_router)
