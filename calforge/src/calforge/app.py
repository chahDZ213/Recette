"""Composition root.

``ApplicationContext`` wires the whole application together exactly once:
configuration, logging, database (migrated), blob store, plugins and
services. The UI and tests both bootstrap through this class, which is the
only place allowed to construct concrete infrastructure.
"""

from __future__ import annotations

import logging

from calforge.core.config import AppConfig
from calforge.core.events import EventBus
from calforge.core.logging import setup_logging
from calforge.core.plugins import PluginManager
from calforge.core.registry import ServiceRegistry
from calforge.data.blobstore import BlobStore
from calforge.data.database import Database
from calforge.formats.base import FormatIdentifier
from calforge.formats.generic import GenericBinaryIdentifier
from calforge.services.analysis import AnalysisService
from calforge.services.annotations import AnnotationService
from calforge.services.attachments import AttachmentService
from calforge.services.definitions import DefinitionService
from calforge.services.ecufiles import EcuFileService
from calforge.services.history import HistoryService
from calforge.services.projects import ProjectService
from calforge.services.vehicles import VehicleService

logger = logging.getLogger(__name__)


class ApplicationContext:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.load()
        self.config.ensure_directories()
        setup_logging(self.config.log_dir)
        logger.info("Starting CalForge (data dir: %s)", self.config.data_dir)

        self.bus = EventBus()
        self.registry = ServiceRegistry()
        self.database = Database(self.config)
        self.database.migrate()
        self.blobs = BlobStore(self.config.blob_dir)

        self.plugins = PluginManager()
        identifiers: list[FormatIdentifier] = self.plugins.instances_of(FormatIdentifier)
        if not any(isinstance(i, GenericBinaryIdentifier) for i in identifiers):
            # The generic fallback must exist even if entry-point metadata is
            # unavailable (e.g. running from sources without installation).
            identifiers.append(GenericBinaryIdentifier())

        self.vehicles = VehicleService(self.database, self.bus)
        self.projects = ProjectService(self.database, self.bus)
        self.ecu_files = EcuFileService(self.database, self.blobs, self.bus, identifiers)
        self.attachments = AttachmentService(self.database, self.blobs, self.bus)
        self.history = HistoryService(self.database, self.bus)
        self.annotations = AnnotationService(self.database, self.bus)
        self.analysis = AnalysisService(self.database, self.ecu_files, self.bus)
        self.definitions = DefinitionService(self.database, self.ecu_files, self.bus)

        for interface, instance in (
            (VehicleService, self.vehicles),
            (ProjectService, self.projects),
            (EcuFileService, self.ecu_files),
            (AttachmentService, self.attachments),
            (HistoryService, self.history),
            (AnnotationService, self.annotations),
            (AnalysisService, self.analysis),
            (DefinitionService, self.definitions),
        ):
            self.registry.register(interface, instance)

    def shutdown(self) -> None:
        logger.info("Shutting down CalForge")
        try:
            self.database.run_scheduled_backup()
        except Exception:
            logger.exception("Backup on shutdown failed")
        self.database.dispose()
