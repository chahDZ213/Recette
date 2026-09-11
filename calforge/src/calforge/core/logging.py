"""Centralised logging setup.

Every module logs through ``logging.getLogger(__name__)``. This module only
configures handlers: a rotating file (complete history, DEBUG) and the console
(INFO). The UI attaches its own handler to stream records into the log
console dock without touching this configuration.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s %(threadName)s :: %(message)s"

_configured = False


def setup_logging(log_dir: Path, *, console_level: int = logging.INFO) -> None:
    """Configure the root logger. Idempotent so tests can call it freely."""
    global _configured
    if _configured:
        return
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "calforge.log", maxBytes=5_000_000, backupCount=10, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setLevel(console_level)
    console.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(console)

    # SQLAlchemy is chatty at INFO through its own loggers; keep the file
    # readable while still recording slow-query warnings.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    _configured = True
