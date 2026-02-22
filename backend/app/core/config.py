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
    admin_username: str = Field(default="admin", alias="ADMIN_USERNAME")
    admin_password: str = Field(default="admin123", alias="ADMIN_PASSWORD")
    storage_dir: str = Field(default="storage", alias="STORAGE_DIR")


settings = Settings()
