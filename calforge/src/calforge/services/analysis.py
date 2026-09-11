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
from calforge.services.dto import EcuFileDto, MapCandidateDto
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

    def edit_map(
        self,
        candidate_id: int,
        new_values: np.ndarray,
        *,
        output_filename: str | None = None,
    ) -> EcuFileDto:
        """Write ``new_values`` into the candidate's block and save the result
        as a NEW modified file (the original is never altered — ADR-0003).

        ``new_values`` must match the candidate's shape; values are clamped to
        the storage type's range. Returns the new file's DTO.
        """
        candidate = self.get_candidate(candidate_id)
        if new_values.shape != (candidate.rows, candidate.cols):
            raise ValueError(
                f"Dimensions {new_values.shape} incompatibles avec la "
                f"cartographie {candidate.rows}×{candidate.cols}."
            )
        original = self._files.read_content(candidate.ecu_file_id)
        edited = mapdetect.encode_block(
            original,
            candidate.offset,
            new_values,
            candidate.element_size,
            candidate.endianness,
        )
        parent = self._files.get(candidate.ecu_file_id)
        name = output_filename or self._derived_name(parent.original_filename)
        map_label = candidate.name or f"0x{candidate.offset:X}"
        dto = self._files.create_derivative(
            candidate.ecu_file_id,
            edited,
            name,
            notes=f"Cartographie « {map_label} » modifiée depuis {parent.original_filename}.",
        )
        logger.info(
            "Map %r edited on file #%d -> new file #%d",
            map_label, candidate.ecu_file_id, dto.id,
        )
        return dto

    def scale_map(
        self, candidate_id: int, percent: float, *, output_filename: str | None = None
    ) -> EcuFileDto:
        """Scale every cell of a map by ``percent`` % (common tuning op) and
        save as a new file. +10 means ×1.10."""
        values = self.read_map_values(candidate_id)
        scaled = values.astype(np.float64) * (1.0 + percent / 100.0)
        return self.edit_map(candidate_id, scaled, output_filename=output_filename)

    @staticmethod
    def _derived_name(parent_name: str) -> str:
        stem, dot, ext = parent_name.rpartition(".")
        base = stem if dot else parent_name
        suffix = f".{ext}" if dot else ""
        return f"{base}_modifie{suffix}"
