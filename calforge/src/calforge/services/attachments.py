"""Vehicle attachment service (photos, documents, invoices).

Content is stored in the shared content-addressed blob store (ADR-0003);
deleting an attachment removes the record, never the blob — user data is
sacred, disk space is cheap.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select

from calforge.core.events import EventBus
from calforge.data.blobstore import BlobStore
from calforge.data.database import Database
from calforge.data.models import Attachment, AttachmentCategory
from calforge.services.dto import AttachmentDto
from calforge.services.events import AttachmentAdded, AttachmentDeleted

logger = logging.getLogger(__name__)


class AttachmentNotFoundError(LookupError):
    pass


class AttachmentService:
    def __init__(self, database: Database, blobs: BlobStore, bus: EventBus) -> None:
        self._db = database
        self._blobs = blobs
        self._bus = bus

    def add(
        self,
        vehicle_id: int,
        source: Path,
        *,
        category: AttachmentCategory = AttachmentCategory.OTHER,
        notes: str = "",
    ) -> AttachmentDto:
        stored = self._blobs.store_file(source)
        with self._db.session() as session:
            record = Attachment(
                vehicle_id=vehicle_id,
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                original_filename=source.name,
                category=category.value,
                notes=notes,
            )
            session.add(record)
            session.flush()
            dto = AttachmentDto.model_validate(record)
        logger.info("Attached %r to vehicle #%d (%s)", source.name, vehicle_id, category.value)
        self._bus.publish(AttachmentAdded(attachment=dto))
        return dto

    def list_for_vehicle(self, vehicle_id: int) -> list[AttachmentDto]:
        with self._db.session() as session:
            stmt = (
                select(Attachment)
                .where(Attachment.vehicle_id == vehicle_id)
                .order_by(Attachment.created_at.desc())
            )
            return [AttachmentDto.model_validate(a) for a in session.scalars(stmt)]

    def get(self, attachment_id: int) -> AttachmentDto:
        with self._db.session() as session:
            record = session.get(Attachment, attachment_id)
            if record is None:
                raise AttachmentNotFoundError(attachment_id)
            return AttachmentDto.model_validate(record)

    def read_content(self, attachment_id: int) -> bytes:
        return self._blobs.read_bytes(self.get(attachment_id).sha256, verify=True)

    def export_to(self, attachment_id: int, target: Path) -> Path:
        """Copy the attachment out of the store (e.g. to open or share it)."""
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.read_content(attachment_id))
        return target

    def delete(self, attachment_id: int) -> None:
        dto = self.get(attachment_id)
        with self._db.session() as session:
            record = session.get(Attachment, attachment_id)
            if record is not None:
                session.delete(record)
        logger.info("Deleted attachment #%d (blob kept)", attachment_id)
        self._bus.publish(
            AttachmentDeleted(attachment_id=attachment_id, vehicle_id=dto.vehicle_id)
        )
