"""Background execution for the UI.

Services are thread-safe, so any potentially slow call (imports, diffs,
hashing) is wrapped in a ``Worker`` and dispatched on the global
``QThreadPool``. Results and errors come back on the GUI thread through
queued signal connections — UI code never touches locks.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

logger = logging.getLogger(__name__)


class _WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class Worker(QRunnable):
    def __init__(self, fn: Callable[[], object]) -> None:
        super().__init__()
        self._fn = fn
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:
            logger.exception("Background task failed")
            self.signals.failed.emit(str(exc))
        else:
            self.signals.finished.emit(result)


def run_in_background(
    fn: Callable[[], object],
    on_done: Callable[[object], None],
    on_error: Callable[[str], None],
) -> None:
    worker = Worker(fn)
    worker.signals.finished.connect(on_done)
    worker.signals.failed.connect(on_error)
    QThreadPool.globalInstance().start(worker)
