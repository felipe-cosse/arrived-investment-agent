"""Runtime configuration via pydantic-settings; every variable is listed in §13.

Values come from the environment (or an optional `.env` file in dev); secrets
are never read from anywhere else (R23). Tests construct `Settings` directly
with keyword arguments, which take priority over the environment.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# The Zillow adapter owns its default CSV URLs; app importing infrastructure is
# the same inward direction the composition root uses (§3, R3).
from infrastructure.enrichment.zillow import ZHVI_DEFAULT_URL, ZORI_DEFAULT_URL


class Settings(BaseSettings):
    """Environment-driven application settings (spec §13)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str | None = None  # required for /api/chat only
    anthropic_model: str = "claude-sonnet-5"
    max_tokens: int = 4096
    max_agent_turns: int = 8
    # Server-side truncation (R17): >= 1 so the limit can never disable truncation.
    max_history_messages: int = Field(default=40, ge=1)
    db_path: Path = Path("data/arrived.duckdb")
    cors_origins: str = "http://localhost:5173"  # comma-separated; dev only
    fred_api_key: str | None = None
    census_api_key: str | None = None
    zillow_zhvi_url: str = ZHVI_DEFAULT_URL
    zillow_zori_url: str = ZORI_DEFAULT_URL

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS_ORIGINS split on commas with blanks dropped."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
