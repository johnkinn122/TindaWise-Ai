"""Application settings, loaded from environment variables (and .env in development)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
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
    # A public demo (docs/DEPLOYMENT.md): sign-up is off, and the seed scripts may write the
    # sample stores and their public demo accounts even though `environment` is production.
    demo_mode: bool = False

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _use_psycopg(cls, url: str) -> str:
        """Hosts such as Neon hand out `postgresql://` or `postgres://` URLs. SQLAlchemy reads
        those as the psycopg2 driver, which isn't installed; this app uses psycopg 3. Query
        parameters such as `sslmode=require` are kept and passed to the driver."""
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url.removeprefix(prefix)
        return url

    @property
    def sample_data_allowed(self) -> bool:
        """The seed scripts create stores with public demo passwords: only off production, or on
        a production server that is the public demo."""
        return self.environment != "production" or self.demo_mode

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
