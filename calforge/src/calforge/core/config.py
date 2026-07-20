"""Application configuration.

Configuration is a validated Pydantic model persisted as TOML in the user's
configuration directory. Every path the application writes to derives from
this module so that tests (and portable installs) can redirect the whole
application to a temporary directory by constructing ``AppConfig`` manually.
"""

from __future__ import annotations

import logging
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Self

import tomli_w
from platformdirs import user_config_dir, user_data_dir, user_log_dir
from pydantic import BaseModel, Field, ValidationError

from calforge import APP_NAME

logger = logging.getLogger(__name__)

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


class AiConfig(BaseModel):
    """AI assistant configuration.

    ``provider`` selects the default assistant backend by name. ``offline``
    (a deterministic local analyst) is always available and requires no
    network or key. The Claude provider activates only when an API key is
    present (``api_key`` here or the ``ANTHROPIC_API_KEY`` environment
    variable) and the ``anthropic`` SDK is installed. The key is never
    written to the config file by default — leave it empty and use the
    environment variable to avoid storing secrets on disk.
    """

    provider: str = "offline"
    model: str = "claude-sonnet-5"
    api_key: str = ""
    max_tokens: int = 1024


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
    ai: AiConfig = Field(default_factory=AiConfig)

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
        always be able to start. A corrupt or invalid file is preserved
        (renamed to ``*.corrupt-<stamp>``) so the user can recover it, the
        problem is logged, and defaults are used.
        """
        path = config_path or cls.default_config_path()
        if not path.is_file():
            config = cls(config_path=path)
            config.save()
            return config
        try:
            with path.open("rb") as fh:
                raw = tomllib.load(fh)
            config = cls.model_validate(raw)
            config.config_path = path
            return config
        except (OSError, tomllib.TOMLDecodeError, ValidationError) as exc:
            logger.warning("Configuration invalide (%s) : %s — défauts utilisés.", path, exc)
            try:
                stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
                path.replace(path.with_name(f"{path.name}.corrupt-{stamp}"))
            except OSError:
                logger.exception("Impossible de mettre de côté la configuration corrompue.")
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
