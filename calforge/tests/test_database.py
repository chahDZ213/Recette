from __future__ import annotations

import sqlite3

from calforge.app import ApplicationContext
from calforge.core.config import AppConfig
from calforge.data.database import Database


def test_migrations_create_schema(app_config: AppConfig) -> None:
    database = Database(app_config)
    database.migrate()
    try:
        with sqlite3.connect(app_config.database_path) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        assert {"vehicles", "projects", "ecu_files", "alembic_version"} <= tables
    finally:
        database.dispose()


def test_migrate_is_idempotent(app_config: AppConfig) -> None:
    database = Database(app_config)
    database.migrate()
    database.migrate()  # second run must be a no-op, not an error
    database.dispose()


def test_backup_produces_consistent_copy(context: ApplicationContext) -> None:
    from calforge.services.dto import VehicleInput

    context.vehicles.create(VehicleInput(make="Seat", model="Leon Cupra"))
    target = context.database.run_scheduled_backup()

    assert target is not None and target.is_file()
    with sqlite3.connect(target) as conn:
        count = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
    assert count == 1


def test_backup_pruning_respects_keep_last(app_config: AppConfig) -> None:
    app_config.backup.keep_last = 2
    database = Database(app_config)
    database.migrate()
    try:
        for _ in range(4):
            database.backup_to(
                app_config.backup_dir / f"calforge-fake-{_}.db"
            )
        database.run_scheduled_backup()
        remaining = list(app_config.backup_dir.glob("calforge-*.db"))
        assert len(remaining) == 2
    finally:
        database.dispose()


def test_config_roundtrip(tmp_path) -> None:
    config_path = tmp_path / "calforge.toml"
    config = AppConfig(
        data_dir=tmp_path / "data", log_dir=tmp_path / "logs", config_path=config_path
    )
    config.save()

    loaded = AppConfig.load(config_path)
    assert loaded.data_dir == config.data_dir
    assert loaded.backup.keep_last == config.backup.keep_last
