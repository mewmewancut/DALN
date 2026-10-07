from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fashion E-Commerce API"
    database_url: str = "postgresql+psycopg://fashion:fashion@localhost:5432/fashion"
    test_database_url: str = "postgresql+psycopg://fashion:fashion@localhost:5432/fashion_test"
    jwt_secret: str = "change-me-before-production-use-at-least-32-characters"
    jwt_expire_minutes: int = 60
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_app_password: str = ""
    email_from_name: str = "Fashion E-Commerce"
    frontend_public_url: str = "http://localhost:5173"
    verify_email_expire_minutes: int = 480
    reset_password_expire_minutes: int = 30
    smtp_timeout_seconds: int = 10
    genie_config_path: str = ""
    product_image_directory: str = "runtime/product-images"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
