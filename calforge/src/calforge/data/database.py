"""Database lifecycle: engine construction, migrations, sessions, backups.

SQLite is configured for durability and concurrency (WAL journal, foreign
keys, busy timeout). All application code obtains sessions from
``Database.session()`` — a context manager that commits on success and rolls
back on error — so transaction boundaries are always explicit and short.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from calforge.core.config import AppConfig

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Database:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        config.ensure_directories()
        self._engine = create_engine(
            f"sqlite:///{config.database_path}",
            connect_args={"timeout": config.database.busy_timeout_ms / 1000},
        )
        event.listen(self._engine, "connect", self._on_connect)
        self._session_factory = sessionmaker(
            bind=self._engine, expire_on_commit=False, autoflush=False
        )

    @staticmethod
    def _on_connect(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    def migrate(self) -> None:
        """Bring the schema to the latest revision. Safe to run on every start."""
        alembic_cfg = AlembicConfig()
        alembic_cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
        alembic_cfg.attributes["engine"] = self._engine
        logger.info("Running database migrations on %s", self._config.database_path)
        alembic_command.upgrade(alembic_cfg, "head")

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def backup_to(self, target: Path) -> None:
        """Consistent online backup using SQLite's backup API (WAL-safe)."""
        import sqlite3

        target.parent.mkdir(parents=True, exist_ok=True)
        raw = self._engine.raw_connection()
        try:
            with sqlite3.connect(target) as dest:
                raw.driver_connection.backup(dest)
        finally:
            raw.close()
        logger.info("Database backed up to %s", target)

    def run_scheduled_backup(self) -> Path | None:
        """Create a timestamped backup and prune old ones per configuration."""
        cfg = self._config.backup
        if not cfg.enabled:
            return None
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        target = self._config.backup_dir / f"calforge-{stamp}.db"
        self.backup_to(target)
        backups = sorted(self._config.backup_dir.glob("calforge-*.db"))
        for old in backups[: max(0, len(backups) - cfg.keep_last)]:
            old.unlink(missing_ok=True)
        return target

    def dispose(self) -> None:
        self._engine.dispose()
