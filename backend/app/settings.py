"""Single backend configuration entry point. Never opens a database connection."""
from functools import lru_cache
import os
from pathlib import Path
import re
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


LOCAL_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None, env_file_encoding="utf-8", extra="forbid",
        hide_input_in_errors=True, frozen=True,
    )

    app_env: Literal["development", "test", "production"] = "development"
    debug: bool = False
    db_host: str = "127.0.0.1"
    db_port: int = Field(default=15432, ge=1, le=65535)
    db_name: str = "personal_web_dev"
    db_user: str = "personal_web_dev"
    # Existing APIs do not use a database yet. A local password may stay blank
    # until database integration; production must always explicitly supply it.
    db_password: SecretStr = Field(default_factory=lambda: SecretStr(""), repr=False, exclude=True)

    # Used only by the explicit local development launcher, never by FastAPI.
    dev_ssh_host: str = ""
    dev_ssh_user: str = "ubuntu"
    dev_ssh_port: int = Field(default=22, ge=1, le=65535)
    dev_db_remote_port: int = Field(default=5432, ge=1, le=65535)
    dev_backend_port: int = Field(default=8010, ge=1, le=65535)

    @field_validator("dev_ssh_host", "dev_ssh_user")
    @classmethod
    def ssh_target(cls, value: str, info) -> str:
        value = value.strip()
        if not value and info.field_name == "dev_ssh_host":
            return value
        pattern = r"[A-Za-z0-9_][A-Za-z0-9_.:-]*" if info.field_name == "dev_ssh_host" else r"[A-Za-z0-9_][A-Za-z0-9_.-]*"
        if not re.fullmatch(pattern, value):
            raise ValueError("SSH host/user must be a hostname, address or SSH config alias and a valid username")
        return value

    @field_validator("db_host", "db_name", "db_user")
    @classmethod
    def nonblank_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("database host, name and user must not be blank")
        return value

    @model_validator(mode="after")
    def production_requirements(self) -> "Settings":
        if self.app_env == "production":
            required = {"db_host", "db_port", "db_name", "db_user", "db_password"}
            if not required.issubset(self.model_fields_set):
                raise ValueError("production requires explicit DB_HOST, DB_PORT, DB_NAME, DB_USER and DB_PASSWORD")
            if not self.db_password.get_secret_value().strip():
                raise ValueError("DB_PASSWORD must not be blank in production")
            if self.debug:
                raise ValueError("DEBUG must be false in production")
        return self


@lru_cache
def get_settings() -> Settings:
    """Environment overrides the fixed local file; test/production never read it."""
    environment = os.environ.get("APP_ENV", "development")
    settings = Settings(_env_file=LOCAL_ENV_FILE if environment == "development" else None)
    if settings.app_env != environment:
        raise ValueError("Select test or production through the APP_ENV process environment, not the local .env file")
    return settings
