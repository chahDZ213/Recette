"""Alembic environment. Invoked programmatically by ``Database.migrate()``,
which passes the live engine through ``config.attributes["engine"]``."""

from __future__ import annotations

from alembic import context

from calforge.data.models import Base

target_metadata = Base.metadata


def run_migrations() -> None:
    engine = context.config.attributes.get("engine")
    if engine is None:
        raise RuntimeError(
            "CalForge migrations must be run through Database.migrate(), "
            "which provides the engine."
        )
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # required for ALTER TABLE on SQLite
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
