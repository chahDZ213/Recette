"""UI bootstrap: QApplication + ApplicationContext + MainWindow."""

from __future__ import annotations

import logging

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from calforge import APP_NAME
from calforge.app import ApplicationContext
from calforge.ui.main_window import MainWindow
from calforge.ui.theme import apply_dark_theme

logger = logging.getLogger(__name__)


def run(argv: list[str]) -> int:
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    apply_dark_theme(app)

    context = ApplicationContext()

    window = MainWindow(context)
    window.show()

    # Periodic automatic backups on the GUI timer; the SQLite backup API is
    # incremental and cheap, so this never blocks the interface noticeably.
    backup_timer = QTimer(window)
    interval_minutes = context.config.backup.interval_minutes
    if context.config.backup.enabled and interval_minutes > 0:
        backup_timer.setInterval(interval_minutes * 60_000)
        backup_timer.timeout.connect(context.database.run_scheduled_backup)
        backup_timer.start()

    exit_code = app.exec()
    context.shutdown()
    return exit_code
