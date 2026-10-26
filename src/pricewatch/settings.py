from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str = "pricewatch"
    postgres_password: str = "pricewatch"
    postgres_db: str = "pricewatch"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    log_level: str = "INFO"
    crawler_config_path: Path = Path("config/crawler.yaml")
    selectors_path: Path = Path("config/selectors.yaml")
    landing_dir: Path = Path("data/landing")
    sample_dir: Path = Path("sample_data")
    alert_webhook_url: str | None = None
    skip_live_crawl: bool = False

    @field_validator("alert_webhook_url")
    @classmethod
    def blank_is_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value else None

    def database_url(self, user: str | None = None, password: str | None = None) -> str:
        return (
            f"postgresql://{user or self.postgres_user}:{password or self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


class HealthConfig(BaseModel):
    parse_success_rate_threshold: float = 0.90


class CrawlerConfig(BaseModel):
    user_agent: str
    request_timeout_seconds: float = 20
    delay_seconds: float = 3.0
    delay_jitter_seconds: float = 1.5
    max_attempts: int = 3
    max_pages: int = 10
    min_hours_between_live_runs: float = 10
    health: HealthConfig = HealthConfig()


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_crawler_config(path: Path | str | None = None) -> CrawlerConfig:
    path = path or get_settings().crawler_config_path
    with open(path, encoding="utf-8") as f:
        return CrawlerConfig(**yaml.safe_load(f))


def load_selectors(path: Path | str | None = None) -> dict[str, Any]:
    path = path or get_settings().selectors_path
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
