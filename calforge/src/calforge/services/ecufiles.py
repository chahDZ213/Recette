"""ECU file import and analysis service.

Importing a file is a pipeline:

1. hash + copy into the content-addressed blob store (deduplicated),
2. run the format identification pipeline (facts vs hypotheses, ADR-0004),
3. persist metadata and publish ``EcuFileImported``.

The whole pipeline is CPU/IO bound and thread-safe; the UI runs it on a
worker thread.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import select

from calforge.analysis.diff import DiffResult, diff_bytes
from calforge.core.events import EventBus
from calforge.data.blobstore import BlobStore
from calforge.data.database import Database
from calforge.data.models import EcuFile, EcuFileKind
from calforge.formats.base import FormatIdentifier, run_identification
from calforge.services.dto import EcuFileDto
from calforge.services.events import EcuFileImported

logger = logging.getLogger(__name__)


class EcuFileNotFoundError(LookupError):
    pass


class EcuFileService:
    def __init__(
        self,
        database: Database,
        blobs: BlobStore,
        bus: EventBus,
        identifiers: list[FormatIdentifier],
    ) -> None:
        self._db = database
        self._blobs = blobs
        self._bus = bus
        self._identifiers = identifiers

    def import_file(
        self,
        source: Path,
        *,
        vehicle_id: int | None = None,
        project_id: int | None = None,
        kind: EcuFileKind = EcuFileKind.UNKNOWN,
        notes: str = "",
    ) -> EcuFileDto:
        stored = self._blobs.store_file(source)
        data = self._blobs.read_bytes(stored.sha256)
        report = run_identification(self._identifiers, source, data)

        with self._db.session() as session:
            record = EcuFile(
                vehicle_id=vehicle_id,
                project_id=project_id,
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                original_filename=source.name,
                kind=kind.value,
                format_name=report.format_name,
                identified_facts=dict(report.facts),
                hypotheses=[asdict(h) for h in report.hypotheses],
                notes=notes,
            )
            session.add(record)
            session.flush()
            dto = EcuFileDto.model_validate(record)

        logger.info(
            "Imported ECU file %r as #%d (sha256=%s, dedup=%s)",
            source.name,
            dto.id,
            stored.sha256[:12],
            stored.already_existed,
        )
        self._bus.publish(EcuFileImported(ecu_file=dto, deduplicated=stored.already_existed))
        return dto

    def get(self, file_id: int) -> EcuFileDto:
        with self._db.session() as session:
            record = session.get(EcuFile, file_id)
            if record is None:
                raise EcuFileNotFoundError(file_id)
            return EcuFileDto.model_validate(record)

    def list_all(self) -> list[EcuFileDto]:
        with self._db.session() as session:
            stmt = select(EcuFile).order_by(EcuFile.created_at.desc())
            return [EcuFileDto.model_validate(f) for f in session.scalars(stmt)]

    def list_for_vehicle(self, vehicle_id: int) -> list[EcuFileDto]:
        with self._db.session() as session:
            stmt = (
                select(EcuFile)
                .where(EcuFile.vehicle_id == vehicle_id)
                .order_by(EcuFile.created_at.desc())
            )
            return [EcuFileDto.model_validate(f) for f in session.scalars(stmt)]

    def read_content(self, file_id: int) -> bytes:
        """Load the binary content of a file (integrity-checked)."""
        dto = self.get(file_id)
        return self._blobs.read_bytes(dto.sha256, verify=True)

    def compare(self, file_id_a: int, file_id_b: int) -> DiffResult:
        """Byte-level comparison of two imported files."""
        return diff_bytes(self.read_content(file_id_a), self.read_content(file_id_b))
