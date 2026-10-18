from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://cable:cable_dev_change_me@localhost:5432/cable"
    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 60 * 12
    admin_email: str = "admin@example.com"
    admin_password: str = "changeme"
    appdata_dir: str = "data/appdata"
    cors_origins: str = "http://localhost:3000,http://localhost"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def appdata_path(self) -> Path:
        path = Path(self.appdata_dir)
        path.mkdir(parents=True, exist_ok=True)
        (path / "uploads").mkdir(exist_ok=True)
        (path / "datasets").mkdir(exist_ok=True)
        return path


settings = Settings()
