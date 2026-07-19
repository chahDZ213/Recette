"""Tests for v0.3 services: annotations and map candidate lifecycle."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.test_mapdetect import build_synthetic_dump

from calforge.app import ApplicationContext
from calforge.data.models import AnnotationKind, MapCandidateStatus
from calforge.services.annotations import AnnotationNotFoundError
from calforge.services.dto import AnnotationInput, VehicleInput
from calforge.services.events import AnnotationAdded, MapCandidatesRefreshed


@pytest.fixture
def imported_dump(context: ApplicationContext, tmp_path: Path):
    data, expected_offset = build_synthetic_dump()
    path = tmp_path / "dump_with_map.bin"
    path.write_bytes(data)
    vehicle = context.vehicles.create(VehicleInput(make="Seat", model="Leon"))
    dto = context.ecu_files.import_file(path, vehicle_id=vehicle.id)
    return dto, expected_offset


class TestAnnotations:
    def test_add_list_delete(self, context: ApplicationContext, imported_dump) -> None:
        file, _ = imported_dump
        received = []
        context.bus.subscribe(AnnotationAdded, received.append)

        dto = context.annotations.add(
            AnnotationInput(
                ecu_file_id=file.id,
                offset=0x100,
                length=32,
                kind=AnnotationKind.BOOKMARK,
                title="Zone checksum",
                comment="À vérifier après chaque modification",
            )
        )

        assert dto.end == 0x120
        assert len(received) == 1
        assert [a.id for a in context.annotations.list_for_file(file.id)] == [dto.id]

        context.annotations.delete(dto.id)
        assert context.annotations.list_for_file(file.id) == []
        with pytest.raises(AnnotationNotFoundError):
            context.annotations.delete(dto.id)

    def test_blank_title_rejected(self, imported_dump) -> None:
        file, _ = imported_dump
        with pytest.raises(ValueError):
            AnnotationInput(ecu_file_id=file.id, offset=0, title="  ")


class TestMapCandidateLifecycle:
    def test_detect_persists_proposals(self, context: ApplicationContext, imported_dump) -> None:
        file, expected_offset = imported_dump
        events = []
        context.bus.subscribe(MapCandidatesRefreshed, events.append)

        candidates = context.analysis.detect_maps(file.id)

        assert any(c.offset == expected_offset for c in candidates)
        assert all(c.status == MapCandidateStatus.PROPOSED for c in candidates)
        assert len(events) == 1
        # Persisted: a fresh listing returns the same rows.
        assert [c.id for c in context.analysis.list_candidates(file.id)] == [
            c.id for c in candidates
        ]

    def test_validation_survives_redetection(
        self, context: ApplicationContext, imported_dump
    ) -> None:
        file, expected_offset = imported_dump
        candidates = context.analysis.detect_maps(file.id)
        target = next(c for c in candidates if c.offset == expected_offset)

        validated = context.analysis.set_candidate_status(
            target.id, MapCandidateStatus.VALIDATED, name="Injection charge/régime"
        )
        assert validated.status == MapCandidateStatus.VALIDATED
        assert validated.name == "Injection charge/régime"

        # Re-run detection: the human decision must survive, un-decided
        # proposals are refreshed, and no new proposal may overlap it.
        after = context.analysis.detect_maps(file.id)
        survivors = [c for c in after if c.id == target.id]
        assert survivors and survivors[0].status == MapCandidateStatus.VALIDATED
        for candidate in after:
            if candidate.id == target.id:
                continue
            assert candidate.end <= validated.offset or candidate.offset >= validated.end

    def test_read_map_values_decodes_block(
        self, context: ApplicationContext, imported_dump
    ) -> None:
        file, expected_offset = imported_dump
        candidates = context.analysis.detect_maps(file.id)
        target = next(c for c in candidates if c.offset == expected_offset)

        values = context.analysis.read_map_values(target.id)

        assert values.shape == (target.rows, target.cols)
        assert values[0, 0] == 1000  # planted base value
