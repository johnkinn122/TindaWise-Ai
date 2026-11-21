"""Application settings, loaded from environment variables (and .env in development)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://tindawise:tindawise_dev@localhost:5433/tindawise"
    test_database_url: str = (
        "postgresql+psycopg://tindawise:tindawise_dev@localhost:5433/tindawise_test"
    )
    cors_origins: str = Field(default="http://localhost:3000")
    session_ttl_days: int = 30

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
