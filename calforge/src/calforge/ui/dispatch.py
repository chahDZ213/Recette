"""Bridges between the (thread-agnostic) event bus / logging and the GUI thread."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from calforge.core.events import Event, EventBus


class EventBridge(QObject):
    """Re-emits domain events as a Qt signal.

    Bus handlers may run on worker threads; the queued nature of cross-thread
    signal connections guarantees ``event_received`` slots run on the GUI
    thread. Widgets connect to ``event_received`` and dispatch on the event
    type.
    """

    event_received = Signal(object)

    def __init__(self, bus: EventBus, event_types: list[type[Event]], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._unsubscribers = [bus.subscribe(et, self._on_event) for et in event_types]

    def _on_event(self, event: Event) -> None:
        self.event_received.emit(event)

    def detach(self) -> None:
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()


class QtLogHandler(logging.Handler, QObject):
    """Streams log records into the UI log console, thread-safely."""

    record_emitted = Signal(str)

    def __init__(self) -> None:
        logging.Handler.__init__(self, level=logging.INFO)
        QObject.__init__(self)
        self.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.record_emitted.emit(self.format(record))
        except Exception:  # pragma: no cover - never raise from logging
            self.handleError(record)
