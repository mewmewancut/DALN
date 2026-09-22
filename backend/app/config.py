from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fashion E-Commerce API"
    database_url: str = "postgresql+psycopg://fashion:fashion@localhost:5432/fashion"
    test_database_url: str = (
        "postgresql+psycopg://fashion:fashion@localhost:5432/fashion_test"
    )
    jwt_secret: str = "change-me-before-production-use-at-least-32-characters"
    jwt_expire_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
