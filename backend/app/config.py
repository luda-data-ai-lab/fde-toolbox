import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    app_env: Literal["development", "test", "production"] = "development"
    db_type: Literal["sqlite", "postgresql", "mssql"] = "sqlite"
    database_url: str = "sqlite:///./data/fde.db"
    data_dir: Path = Path("./data")
    secret_key: str = Field(min_length=32)
    encryption_key: str = Field(min_length=16)
    deployment_mode: Literal["standalone", "hosted"] = "standalone"
    adapters_allowed: bool = False
    max_upload_mb: int = 20
    allowed_upload_extensions: str = "pdf,png,jpg,jpeg,gif,txt,md,csv,json,xlsx,xlsm,xls,docx,pptx,zip,log"
    default_locale: str = "ko"
    deployment_base_iri: str = "https://ludaresearch.org/onto/"
    session_cookie_name: str = "fde_session"
    session_ttl_minutes: int = 60 * 12
    cookie_secure: bool = False
    static_dir: Path | None = None

    @property
    def upload_extensions(self) -> set[str]:
        return {e.strip().lower().lstrip(".") for e in self.allowed_upload_extensions.split(",") if e.strip()}


@lru_cache
def get_settings() -> Settings:
    # FDE_SECRETS_DIR: directory of files named after settings (e.g. secret_key), Docker-secrets style.
    return Settings(_secrets_dir=os.environ.get("FDE_SECRETS_DIR") or None)
