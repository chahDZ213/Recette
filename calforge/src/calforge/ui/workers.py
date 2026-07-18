"""Background execution for the UI.

Services are thread-safe, so any potentially slow call (imports, diffs,
hashing) is wrapped in a ``Worker`` and dispatched on the global
``QThreadPool``. Results and errors come back on the GUI thread through
queued signal connections — UI code never touches locks.

Lifetime note: Qt auto-deletes a ``QRunnable`` as soon as ``run()`` returns,
which would destroy the ``signals`` object *before* its queued cross-thread
emission is delivered — silently dropping every result. ``run_in_background``
therefore disables auto-deletion and keeps a strong reference to the worker
in ``_pending`` until its outcome signal has actually been handled on the
GUI thread.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

logger = logging.getLogger(__name__)

_pending: set[Worker] = set()


class _WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class Worker(QRunnable):
    def __init__(self, fn: Callable[[], object]) -> None:
        super().__init__()
        self._fn = fn
        self.signals = _WorkerSignals()
        self.setAutoDelete(False)

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
    _pending.add(worker)

    def _finish(result: object) -> None:
        try:
            on_done(result)
        finally:
            _pending.discard(worker)

    def _fail(message: str) -> None:
        try:
            on_error(message)
        finally:
            _pending.discard(worker)

    worker.signals.finished.connect(_finish)
    worker.signals.failed.connect(_fail)
    QThreadPool.globalInstance().start(worker)
