from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FITMIND_", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://postgres@127.0.0.1:55432/fitmind"
    dev_login_enabled: bool = False
    session_hours: int = 24
    model_provider: str = "deepseek"
    model_base_url: str = "https://api.deepseek.com"
    model_name: str = "deepseek-flash"
    model_api_key: str = ""
    model_timeout_seconds: int = 35
    wechat_app_id: str = "wx7262dc559800af57"
    wechat_app_secret: str = ""

    @model_validator(mode="after")
    def validate_environment(self):
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("This application requires PostgreSQL with psycopg.")
        if self.environment == "production":
            if not self.wechat_app_id or not self.wechat_app_secret:
                raise ValueError("Production requires WeChat credentials.")
        return self
