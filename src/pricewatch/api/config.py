from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "pricewatch"
    api_db_user: str = "api_app"
    api_db_password: str = "api_app_dev"

    jwt_secret: str = "change-me-to-a-long-random-string-0123456789"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    api_analyst_password_hash: str = ""
    api_admin_password_hash: str = ""

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.api_db_user}:{self.api_db_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_api_settings() -> ApiSettings:
    return ApiSettings()
