"""Application configuration.

Configuration is a validated Pydantic model persisted as TOML in the user's
configuration directory. Every path the application writes to derives from
this module so that tests (and portable installs) can redirect the whole
application to a temporary directory by constructing ``AppConfig`` manually.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Self

import tomli_w
from platformdirs import user_config_dir, user_data_dir, user_log_dir
from pydantic import BaseModel, Field

from calforge import APP_NAME

_CONFIG_FILE_NAME = "calforge.toml"


class DatabaseConfig(BaseModel):
    """SQLite tuning knobs. Kept explicit so a future migration to a
    client/server database only touches this model and the engine factory."""

    filename: str = "calforge.db"
    busy_timeout_ms: int = 5000


class UiConfig(BaseModel):
    theme: str = "dark"
    language: str = "fr"
    restore_layout: bool = True


class BackupConfig(BaseModel):
    enabled: bool = True
    interval_minutes: int = 30
    keep_last: int = 20


class AppConfig(BaseModel):
    """Root configuration object.

    ``data_dir`` contains everything the user must back up (database + blobs).
    ``log_dir`` is disposable. ``config_path`` is where this object was loaded
    from (``None`` for in-memory configurations used in tests).
    """

    data_dir: Path = Field(default_factory=lambda: Path(user_data_dir(APP_NAME)))
    log_dir: Path = Field(default_factory=lambda: Path(user_log_dir(APP_NAME)))
    config_path: Path | None = None
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    ui: UiConfig = Field(default_factory=UiConfig)
    backup: BackupConfig = Field(default_factory=BackupConfig)

    @property
    def database_path(self) -> Path:
        return self.data_dir / self.database.filename

    @property
    def blob_dir(self) -> Path:
        return self.data_dir / "blobs"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"

    def ensure_directories(self) -> None:
        for path in (self.data_dir, self.log_dir, self.blob_dir, self.backup_dir):
            path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def default_config_path(cls) -> Path:
        return Path(user_config_dir(APP_NAME)) / _CONFIG_FILE_NAME

    @classmethod
    def load(cls, config_path: Path | None = None) -> Self:
        """Load configuration from disk, creating a default file on first run.

        An unreadable or invalid file is never fatal: the application must
        always be able to start, so we fall back to defaults and let the
        caller log the problem.
        """
        path = config_path or cls.default_config_path()
        if path.is_file():
            with path.open("rb") as fh:
                raw = tomllib.load(fh)
            config = cls.model_validate(raw)
            config.config_path = path
            return config
        config = cls(config_path=path)
        config.save()
        return config

    def save(self) -> None:
        if self.config_path is None:
            return
        payload = self.model_dump(mode="json", exclude={"config_path"})
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.config_path.with_suffix(".tmp")
        with tmp.open("wb") as fh:
            tomli_w.dump(payload, fh)
        tmp.replace(self.config_path)
