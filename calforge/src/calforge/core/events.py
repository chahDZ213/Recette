"""Thread-safe publish/subscribe event bus.

The bus decouples modules: services publish domain events, the UI (or any
plugin) subscribes without the publisher knowing about it. Events are plain
frozen dataclasses; subscribers are matched on the event *type* (exact class),
which keeps dispatch O(subscribers-of-type) and fully type-checkable.

Handlers run synchronously on the publisher's thread. UI subscribers must
therefore marshal back to the GUI thread themselves (``ui.dispatch`` provides
a helper); keeping the bus policy-free makes it reusable in headless contexts
such as tests, CLI tools and future server deployments.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class Event:
    """Base class for all domain events."""

    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribers: dict[type[Event], list[Callable[[Event], None]]] = defaultdict(list)

    def subscribe[E: Event](self, event_type: type[E], handler: Callable[[E], None]) -> Callable[[], None]:
        """Register ``handler`` for ``event_type``. Returns an unsubscribe callable."""
        with self._lock:
            self._subscribers[event_type].append(handler)  # type: ignore[arg-type]

        def unsubscribe() -> None:
            with self._lock, contextlib.suppress(ValueError):
                self._subscribers[event_type].remove(handler)  # type: ignore[arg-type]

        return unsubscribe

    def publish(self, event: Event) -> None:
        with self._lock:
            handlers = list(self._subscribers.get(type(event), ()))
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                # One faulty subscriber must never break the publisher or
                # the other subscribers.
                logger.exception("Event handler %r failed for %r", handler, event)
