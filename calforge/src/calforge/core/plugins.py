"""Plugin discovery.

CalForge is extended through standard Python entry points in the
``calforge.plugins`` group. Built-in extensions (e.g. the generic binary
format identifier) are registered through the exact same mechanism in
``pyproject.toml``, which guarantees the external plugin path stays exercised
by the application itself.

A plugin entry point must resolve to a callable returning an object; typed
extension points (such as ``calforge.formats.base.FormatIdentifier``) filter
the loaded objects by protocol.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib.metadata import entry_points

logger = logging.getLogger(__name__)

PLUGIN_GROUP = "calforge.plugins"


@dataclass(frozen=True, slots=True)
class LoadedPlugin:
    name: str
    instance: object


class PluginManager:
    def __init__(self, group: str = PLUGIN_GROUP) -> None:
        self._group = group
        self._plugins: list[LoadedPlugin] | None = None

    def load_all(self) -> list[LoadedPlugin]:
        """Discover and instantiate every plugin. Failures are isolated:
        a broken plugin is logged and skipped, never fatal."""
        if self._plugins is not None:
            return self._plugins
        plugins: list[LoadedPlugin] = []
        for ep in entry_points(group=self._group):
            try:
                factory = ep.load()
                plugins.append(LoadedPlugin(name=ep.name, instance=factory()))
                logger.info("Loaded plugin %r", ep.name)
            except Exception:
                logger.exception("Failed to load plugin %r", ep.name)
        self._plugins = plugins
        return plugins

    def instances_of[T](self, protocol: type[T]) -> list[T]:
        return [p.instance for p in self.load_all() if isinstance(p.instance, protocol)]
