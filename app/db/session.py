from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine | None:
    settings = get_settings()
    if not settings.database_url:
        return None
    return create_engine(settings.database_url, pool_pre_ping=True)
