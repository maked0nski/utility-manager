from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="sqlite:///./utility_manager.db",
        alias="DATABASE_URL",
    )
    app_secret_key: str = Field(default="utility-manager-local-secret", alias="APP_SECRET_KEY")
    tenant_access_token_ttl_seconds: int = Field(default=60 * 30, alias="TENANT_ACCESS_TOKEN_TTL_SECONDS")
    tenant_refresh_token_ttl_seconds: int = Field(default=60 * 60 * 24 * 30, alias="TENANT_REFRESH_TOKEN_TTL_SECONDS")
    admin_username: str = Field(default="admin", alias="ADMIN_USERNAME")
    admin_password: str = Field(default="admin123", alias="ADMIN_PASSWORD")
    storage_dir: str = Field(default="storage", alias="STORAGE_DIR")
    legacy_startup_backfill_enabled: bool = Field(default=False, alias="LEGACY_STARTUP_BACKFILL_ENABLED")


settings = Settings()
