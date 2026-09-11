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

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from calforge.analysis.diff import DiffResult, diff_bytes
from calforge.core.events import EventBus
from calforge.data.blobstore import BlobStore
from calforge.data.database import Database
from calforge.data.models import EcuFile, EcuFileKind, Vehicle
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

    @staticmethod
    def _to_dto(record: EcuFile, session: Session) -> EcuFileDto:
        """Build a DTO with display labels while the session is still open."""
        dto = EcuFileDto.model_validate(record)
        updates: dict[str, str] = {}
        if record.vehicle is not None:
            updates["vehicle_label"] = f"{record.vehicle.make} {record.vehicle.model}"
        if record.parent_file_id is not None:
            parent = session.get(EcuFile, record.parent_file_id)
            if parent is not None:
                updates["parent_label"] = parent.original_filename
        return dto.model_copy(update=updates) if updates else dto

    def import_file(
        self,
        source: Path,
        *,
        vehicle_id: int | None = None,
        project_id: int | None = None,
        parent_file_id: int | None = None,
        kind: EcuFileKind = EcuFileKind.UNKNOWN,
        notes: str = "",
    ) -> EcuFileDto:
        stored = self._blobs.store_file(source)
        data = self._blobs.read_bytes(stored.sha256)
        report = run_identification(self._identifiers, source, data)

        if parent_file_id is not None and kind == EcuFileKind.UNKNOWN:
            # A file imported as a version of another one is by definition
            # a modified calibration.
            kind = EcuFileKind.MODIFIED

        with self._db.session() as session:
            if parent_file_id is not None and session.get(EcuFile, parent_file_id) is None:
                raise EcuFileNotFoundError(parent_file_id)
            record = EcuFile(
                vehicle_id=vehicle_id,
                project_id=project_id,
                parent_file_id=parent_file_id,
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
            dto = self._to_dto(record, session)

        logger.info(
            "Imported ECU file %r as #%d (sha256=%s, dedup=%s)",
            source.name,
            dto.id,
            stored.sha256[:12],
            stored.already_existed,
        )
        self._bus.publish(EcuFileImported(ecu_file=dto, deduplicated=stored.already_existed))
        return dto

    def create_derivative(
        self,
        parent_file_id: int,
        data: bytes,
        filename: str,
        *,
        notes: str = "",
    ) -> EcuFileDto:
        """Create a new modified file from in-memory bytes (e.g. an edited map).

        The new file is a MODIFIED derivative of its parent, inherits the
        parent's vehicle/project, and gets a fresh content-addressed blob. The
        parent (and its blob) are never touched (ADR-0003).
        """
        stored = self._blobs.store_bytes(data)
        report = run_identification(self._identifiers, Path(filename), data)
        with self._db.session() as session:
            parent = session.get(EcuFile, parent_file_id)
            if parent is None:
                raise EcuFileNotFoundError(parent_file_id)
            record = EcuFile(
                vehicle_id=parent.vehicle_id,
                project_id=parent.project_id,
                parent_file_id=parent_file_id,
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                original_filename=filename,
                kind=EcuFileKind.MODIFIED.value,
                format_name=report.format_name,
                identified_facts=dict(report.facts),
                hypotheses=[asdict(h) for h in report.hypotheses],
                notes=notes,
            )
            session.add(record)
            session.flush()
            dto = self._to_dto(record, session)
        logger.info(
            "Created modified file %r as #%d from parent #%d (sha256=%s)",
            filename, dto.id, parent_file_id, stored.sha256[:12],
        )
        self._bus.publish(EcuFileImported(ecu_file=dto, deduplicated=stored.already_existed))
        return dto

    def export_to(self, file_id: int, target: Path) -> Path:
        """Write a file's binary content out to disk (integrity-checked)."""
        data = self.read_content(file_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        logger.info("Exported file #%d to %s", file_id, target)
        return target

    def get(self, file_id: int) -> EcuFileDto:
        with self._db.session() as session:
            record = session.get(EcuFile, file_id)
            if record is None:
                raise EcuFileNotFoundError(file_id)
            return self._to_dto(record, session)

    def list_all(self) -> list[EcuFileDto]:
        with self._db.session() as session:
            stmt = (
                select(EcuFile)
                .options(joinedload(EcuFile.vehicle))
                .order_by(EcuFile.created_at.desc())
            )
            return [self._to_dto(f, session) for f in session.scalars(stmt)]

    def list_for_vehicle(self, vehicle_id: int) -> list[EcuFileDto]:
        with self._db.session() as session:
            stmt = (
                select(EcuFile)
                .where(EcuFile.vehicle_id == vehicle_id)
                .order_by(EcuFile.created_at.desc())
            )
            return [self._to_dto(f, session) for f in session.scalars(stmt)]

    def list_derivatives(self, file_id: int) -> list[EcuFileDto]:
        """Direct versions derived from the given file."""
        with self._db.session() as session:
            stmt = (
                select(EcuFile)
                .where(EcuFile.parent_file_id == file_id)
                .order_by(EcuFile.created_at)
            )
            return [self._to_dto(f, session) for f in session.scalars(stmt)]

    def search(self, text: str) -> list[EcuFileDto]:
        """Instant library search: filename, hash, format, vehicle, notes."""
        pattern = f"%{text.strip()}%"
        if pattern == "%%":
            return self.list_all()
        with self._db.session() as session:
            stmt = (
                select(EcuFile)
                .options(joinedload(EcuFile.vehicle))
                .outerjoin(Vehicle, EcuFile.vehicle_id == Vehicle.id)
                .where(
                    or_(
                        EcuFile.original_filename.ilike(pattern),
                        EcuFile.sha256.ilike(pattern),
                        EcuFile.format_name.ilike(pattern),
                        EcuFile.notes.ilike(pattern),
                        Vehicle.make.ilike(pattern),
                        Vehicle.model.ilike(pattern),
                    )
                )
                .order_by(EcuFile.created_at.desc())
            )
            return [self._to_dto(f, session) for f in session.scalars(stmt)]

    def read_content(self, file_id: int) -> bytes:
        """Load the binary content of a file (integrity-checked)."""
        dto = self.get(file_id)
        return self._blobs.read_bytes(dto.sha256, verify=True)

    def compare(self, file_id_a: int, file_id_b: int) -> DiffResult:
        """Byte-level comparison of two imported files."""
        return diff_bytes(self.read_content(file_id_a), self.read_content(file_id_b))
