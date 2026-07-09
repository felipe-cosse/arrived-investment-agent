"""Runtime configuration via pydantic-settings; every variable is listed in §13.

Values come from the environment (or an optional `.env` file in dev); secrets
are never read from anywhere else (R23). Tests construct `Settings` directly
with keyword arguments, which take priority over the environment.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ZHVI_DEFAULT = (
    "https://files.zillowstatic.com/research/public_csvs/zhvi/"
    "Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)
_ZORI_DEFAULT = (
    "https://files.zillowstatic.com/research/public_csvs/zori/"
    "Metro_zori_uc_sfrcondo_sm_sa_month.csv"
)


class Settings(BaseSettings):
    """Environment-driven application settings (spec §13)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str | None = None  # required for /api/chat only
    anthropic_model: str = "claude-sonnet-5"
    max_tokens: int = 4096
    max_agent_turns: int = 8
    max_history_messages: int = 40  # server-side truncation (R17)
    db_path: Path = Path("data/arrived.duckdb")
    cors_origins: str = "http://localhost:5173"  # comma-separated; dev only
    fred_api_key: str | None = None
    census_api_key: str | None = None
    zillow_zhvi_url: str = _ZHVI_DEFAULT
    zillow_zori_url: str = _ZORI_DEFAULT

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS_ORIGINS split on commas with blanks dropped."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
