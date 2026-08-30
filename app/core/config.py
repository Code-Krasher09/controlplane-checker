"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """ControlPlane runtime settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "ControlPlane Checker"
    app_version: str = "0.2.0"
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=True, alias="DEBUG")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # PostgreSQL
    postgres_user: str = Field(default="postgres", alias="POSTGRES_USER")
    postgres_password: str = Field(default="postgres", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="controlplane_db", alias="POSTGRES_DB")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    database_url: Optional[str] = Field(
        default=None,
        alias="DATABASE_URL",
    )

    # Redis
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_url: Optional[str] = Field(
        default=None,
        alias="REDIS_URL",
    )

    # Model Serving / Providers
    model_provider: str = Field(default="mock", alias="MODEL_PROVIDER")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-flash-lite-latest", alias="GEMINI_MODEL")

    # Governance Defaults
    default_max_repair_attempts: int = Field(
        default=2,
        alias="DEFAULT_MAX_REPAIR_ATTEMPTS",
    )
    default_request_cost_budget_usd: float = Field(
        default=0.05,
        alias="DEFAULT_REQUEST_COST_BUDGET_USD",
    )
    default_adjudication_budget_usd: float = Field(
        default=0.02,
        alias="DEFAULT_ADJUDICATION_BUDGET_USD",
    )

    @property
    def async_database_url(self) -> str:
        """Construct async PostgreSQL connection string if not explicitly configured."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        """Construct sync PostgreSQL connection string for Alembic/management."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
