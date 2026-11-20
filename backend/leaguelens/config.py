"""Application settings, read from environment variables (see .env.example)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/leaguelens.db"
    sleeper_base_url: str = "https://api.sleeper.app/v1"
    sleeper_max_rps: float = 10.0
    nflverse_base_url: str = "https://github.com/nflverse/nflverse-data/releases/download"
    cors_origins: str = "http://localhost:5173"
    refresh_interval_minutes: int = 360

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
