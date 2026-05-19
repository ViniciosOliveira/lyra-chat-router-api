from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    app_name: str = "lyra-chat-router-api"
    public_base_url: str = "https://api.grupooliveirarocha.com/googlechat"
    database_url: str | None = None
    google_chat_audience: str = "https://api.grupooliveirarocha.com/googlechat/"
    google_chat_auth_mode: str = "app_url"
    google_chat_dev_bypass_auth: bool = True
    openclaw_forward_enabled: bool = False
    openclaw_forward_url: str | None = None
    openclaw_forward_timeout_seconds: float = 25.0
    openclaw_agent_hook_enabled: bool = False
    openclaw_agent_hook_url: str | None = None
    openclaw_agent_hook_token: str | None = None
    openclaw_agent_hook_agent_id: str = "main"
    openclaw_agent_hook_timeout_seconds: int = 120
    openclaw_agent_hook_request_timeout_seconds: float = 10.0
    google_chat_pubsub_shared_secret: str | None = None
    google_chat_bot_user: str | None = None
    mc_admin_shared_secret: str | None = None

    @property
    def is_prod(self) -> bool:
        return self.app_env.lower() in {"prod", "production"}

    @property
    def effective_mc_admin_secret(self) -> str:
        if self.mc_admin_shared_secret:
            return self.mc_admin_shared_secret
        if not self.is_prod:
            return "dev-admin-secret"
        return ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
