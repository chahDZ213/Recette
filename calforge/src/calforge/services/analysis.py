"""Analysis service: map detection lifecycle and 2D decoding.

Detection replaces previous *proposed* candidates but never touches
*validated* or *rejected* ones — human decisions are permanent until the
human changes them (ADR-0004).
"""

from __future__ import annotations

import logging

import numpy as np
from sqlalchemy import select

from calforge.analysis import mapdetect
from calforge.core.events import EventBus
from calforge.data.database import Database
from calforge.data.models import MapCandidateRecord, MapCandidateStatus
from calforge.services.dto import MapCandidateDto
from calforge.services.ecufiles import EcuFileService
from calforge.services.events import MapCandidatesRefreshed, MapCandidateUpdated

logger = logging.getLogger(__name__)


class MapCandidateNotFoundError(LookupError):
    pass


class AnalysisService:
    def __init__(self, database: Database, ecu_files: EcuFileService, bus: EventBus) -> None:
        self._db = database
        self._files = ecu_files
        self._bus = bus

    def detect_maps(self, ecu_file_id: int) -> list[MapCandidateDto]:
        """Run the detector and persist the resulting proposals."""
        data = self._files.read_content(ecu_file_id)
        found = mapdetect.detect_maps(data)
        logger.info("Map detection on file #%d: %d candidate(s)", ecu_file_id, len(found))

        with self._db.session() as session:
            kept = session.scalars(
                select(MapCandidateRecord).where(
                    MapCandidateRecord.ecu_file_id == ecu_file_id,
                    MapCandidateRecord.status != MapCandidateStatus.PROPOSED.value,
                )
            ).all()
            decided_ranges = [(k.offset, k.offset + k.rows * k.cols * k.element_size) for k in kept]

            for record in session.scalars(
                select(MapCandidateRecord).where(
                    MapCandidateRecord.ecu_file_id == ecu_file_id,
                    MapCandidateRecord.status == MapCandidateStatus.PROPOSED.value,
                )
            ):
                session.delete(record)

            for candidate in found:
                start, end = candidate.offset, candidate.offset + candidate.byte_length
                if any(not (end <= s or start >= e) for s, e in decided_ranges):
                    continue  # a human already ruled on this region
                session.add(
                    MapCandidateRecord(
                        ecu_file_id=ecu_file_id,
                        offset=candidate.offset,
                        rows=candidate.rows,
                        cols=candidate.cols,
                        element_size=candidate.element_size,
                        endianness=candidate.endianness,
                        confidence=candidate.confidence,
                        rationale=candidate.rationale,
                    )
                )

        candidates = self.list_candidates(ecu_file_id)
        self._bus.publish(
            MapCandidatesRefreshed(ecu_file_id=ecu_file_id, candidates=tuple(candidates))
        )
        return candidates

    def list_candidates(self, ecu_file_id: int) -> list[MapCandidateDto]:
        with self._db.session() as session:
            stmt = (
                select(MapCandidateRecord)
                .where(MapCandidateRecord.ecu_file_id == ecu_file_id)
                .order_by(MapCandidateRecord.confidence.desc(), MapCandidateRecord.offset)
            )
            return [MapCandidateDto.model_validate(c) for c in session.scalars(stmt)]

    def get_candidate(self, candidate_id: int) -> MapCandidateDto:
        with self._db.session() as session:
            record = session.get(MapCandidateRecord, candidate_id)
            if record is None:
                raise MapCandidateNotFoundError(candidate_id)
            return MapCandidateDto.model_validate(record)

    def set_candidate_status(
        self, candidate_id: int, status: MapCandidateStatus, *, name: str | None = None
    ) -> MapCandidateDto:
        """Record the human decision on a candidate (validate/reject/reset)."""
        with self._db.session() as session:
            record = session.get(MapCandidateRecord, candidate_id)
            if record is None:
                raise MapCandidateNotFoundError(candidate_id)
            record.status = status.value
            if name is not None:
                record.name = name.strip()
            session.flush()
            dto = MapCandidateDto.model_validate(record)
        logger.info("Candidate #%d marked %s", candidate_id, status.value)
        self._bus.publish(MapCandidateUpdated(candidate=dto))
        return dto

    def read_map_values(self, candidate_id: int) -> np.ndarray:
        """Decode the candidate's block as a rows×cols matrix (for 2D views)."""
        candidate = self.get_candidate(candidate_id)
        data = self._files.read_content(candidate.ecu_file_id)
        return mapdetect.decode_block(
            data,
            candidate.offset,
            candidate.rows,
            candidate.cols,
            candidate.element_size,
            candidate.endianness,
        )
