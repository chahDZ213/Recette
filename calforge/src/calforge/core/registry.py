"""Minimal typed service registry (dependency injection container).

A deliberate alternative to a full DI framework: services are registered once
at composition time (see ``calforge.app.ApplicationContext``) and resolved by
type. This keeps wiring explicit, import-cycle free and trivially replaceable
in tests (register a fake under the same type).
"""

from __future__ import annotations

import threading


class ServiceNotRegisteredError(LookupError):
    pass


class ServiceRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._services: dict[type, object] = {}

    def register[T](self, interface: type[T], instance: T) -> None:
        with self._lock:
            if interface in self._services:
                raise ValueError(f"Service already registered for {interface.__name__}")
            self._services[interface] = instance

    def resolve[T](self, interface: type[T]) -> T:
        with self._lock:
            try:
                return self._services[interface]  # type: ignore[return-value]
            except KeyError:
                raise ServiceNotRegisteredError(interface.__name__) from None
