"""Application configuration with Pydantic BaseSettings and credential safety."""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Google Maps Platform keys
    GOOGLE_MAPS_BROWSER_KEY: Optional[str] = Field(
        default=None,
        description="Public browser key restricted to Maps JavaScript API and HTTP referrers."
    )
    GOOGLE_ROUTES_API_KEY: Optional[str] = Field(
        default=None,
        description="Server-side key for Google Routes API v2."
    )
    GOOGLE_STREET_VIEW_API_KEY: Optional[str] = Field(
        default=None,
        description="Server-side key for Street View Static API."
    )

    # Google Gemini AI settings
    GEMINI_API_KEY: Optional[str] = Field(
        default=None,
        description="Gemini API Key for multimodal road inspection."
    )
    GEMINI_MODEL: str = Field(
        default="gemini-2.5-flash",
        description="Vision-capable Gemini model name."
    )

    # Persistence
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./flowsplit.db",
        description="Database connection string (SQLite for dev/tests, PostgreSQL for prod)."
    )
    REDIS_URL: Optional[str] = Field(
        default=None,
        description="Optional Redis URL for shared caching and distributed allocation."
    )

    # Routing & Vision Parameters
    SAMPLE_INTERVAL_METERS: float = Field(default=100.0, ge=25.0, le=500.0)
    MAX_IMAGE_BUDGET_PER_ROUTE: int = Field(default=10, ge=1, le=30)
    REQUEST_TIMEOUT_SECONDS: float = Field(default=15.0, ge=3.0, le=60.0)
    MAX_RETRIES: int = Field(default=3, ge=1, le=5)

    # Environment
    ENVIRONMENT: str = Field(default="development")
    DEMO_MODE_DEFAULT: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def is_offline_mode_required(self) -> bool:
        """Determines if the backend must default to offline demonstration due to missing keys."""
        return not bool(self.GOOGLE_ROUTES_API_KEY or self.GEMINI_API_KEY)


settings = Settings()
