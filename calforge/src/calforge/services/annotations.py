"""Annotations and bookmarks on ECU file byte ranges."""

from __future__ import annotations

import logging

from sqlalchemy import select

from calforge.core.events import EventBus
from calforge.data.database import Database
from calforge.data.models import Annotation
from calforge.services.dto import AnnotationDto, AnnotationInput
from calforge.services.events import AnnotationAdded, AnnotationDeleted

logger = logging.getLogger(__name__)


class AnnotationNotFoundError(LookupError):
    pass


class AnnotationService:
    def __init__(self, database: Database, bus: EventBus) -> None:
        self._db = database
        self._bus = bus

    def add(self, data: AnnotationInput) -> AnnotationDto:
        with self._db.session() as session:
            record = Annotation(**data.model_dump(mode="json"))
            session.add(record)
            session.flush()
            dto = AnnotationDto.model_validate(record)
        logger.info(
            "Annotation %r added on file #%d at 0x%X", dto.title, dto.ecu_file_id, dto.offset
        )
        self._bus.publish(AnnotationAdded(annotation=dto))
        return dto

    def list_for_file(self, ecu_file_id: int) -> list[AnnotationDto]:
        with self._db.session() as session:
            stmt = (
                select(Annotation)
                .where(Annotation.ecu_file_id == ecu_file_id)
                .order_by(Annotation.offset)
            )
            return [AnnotationDto.model_validate(a) for a in session.scalars(stmt)]

    def delete(self, annotation_id: int) -> None:
        with self._db.session() as session:
            record = session.get(Annotation, annotation_id)
            if record is None:
                raise AnnotationNotFoundError(annotation_id)
            file_id = record.ecu_file_id
            session.delete(record)
        self._bus.publish(
            AnnotationDeleted(annotation_id=annotation_id, ecu_file_id=file_id)
        )
