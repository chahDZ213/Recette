"""Vehicle history timeline service (ADR-0006).

Interventions, diagnostics, road tests, datalogs, calibration steps and notes
share one chronological timeline per vehicle.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from calforge.core.events import EventBus
from calforge.data.database import Database
from calforge.data.models import HistoryEntry
from calforge.services.dto import HistoryEntryDto, HistoryEntryInput
from calforge.services.events import HistoryEntryAdded, HistoryEntryDeleted

logger = logging.getLogger(__name__)


class HistoryEntryNotFoundError(LookupError):
    pass


class HistoryService:
    def __init__(self, database: Database, bus: EventBus) -> None:
        self._db = database
        self._bus = bus

    def add(self, data: HistoryEntryInput) -> HistoryEntryDto:
        with self._db.session() as session:
            # mode="json" turns enums into their stored string values; the
            # datetime must stay a real datetime for the DateTime column.
            payload = data.model_dump(mode="json") | {"occurred_at": data.occurred_at}
            record = HistoryEntry(**payload)
            session.add(record)
            session.flush()
            dto = HistoryEntryDto.model_validate(record)
        logger.info(
            "History entry %r (%s) added to vehicle #%d",
            dto.title,
            dto.entry_type.value,
            dto.vehicle_id,
        )
        self._bus.publish(HistoryEntryAdded(entry=dto))
        return dto

    def list_for_vehicle(self, vehicle_id: int) -> list[HistoryEntryDto]:
        with self._db.session() as session:
            stmt = (
                select(HistoryEntry)
                .where(HistoryEntry.vehicle_id == vehicle_id)
                .order_by(HistoryEntry.occurred_at.desc())
            )
            return [HistoryEntryDto.model_validate(e) for e in session.scalars(stmt)]

    def delete(self, entry_id: int) -> None:
        with self._db.session() as session:
            record = session.get(HistoryEntry, entry_id)
            if record is None:
                raise HistoryEntryNotFoundError(entry_id)
            vehicle_id = record.vehicle_id
            session.delete(record)
        self._bus.publish(HistoryEntryDeleted(entry_id=entry_id, vehicle_id=vehicle_id))
