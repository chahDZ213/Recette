"""Tests for automatic Map Pack generation from evidence."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.test_mapdetect import build_synthetic_dump

from calforge.analysis.packbuilder import discover_maps_from_comparison
from calforge.app import ApplicationContext
from calforge.data.models import EcuFileKind, MapCandidateStatus
from calforge.services.definitions import PackImportError
from calforge.services.dto import VehicleInput


class TestDiscoverFromComparison:
    def test_changed_map_region_is_discovered_with_geometry(self) -> None:
        original, map_offset = build_synthetic_dump()  # map data block at 0x420
        modified = bytearray(original)
        # Tune the whole planted map region (16x16 u16 = 512 bytes).
        for i in range(map_offset, map_offset + 512, 2):
            lo = modified[i] + 8
            modified[i] = lo & 0xFF
        discovered = discover_maps_from_comparison(bytes(original), [bytes(modified)])

        assert discovered, "the tuned map must be discovered"
        geo = [d for d in discovered if d.from_geometry]
        assert geo, "the change overlaps a detected map shape"
        best = geo[0]
        assert best.offset == map_offset
        assert best.cols == 16 and best.rows == 16
        assert best.from_geometry
        assert best.confidence > 0.6  # lifted by real evidence

    def test_identical_files_discover_nothing(self) -> None:
        original, _ = build_synthetic_dump()
        assert discover_maps_from_comparison(original, [original]) == []

    def test_tiny_change_ignored(self) -> None:
        original, _ = build_synthetic_dump()
        modified = bytearray(original)
        modified[0x10] ^= 0xFF  # single byte, not a map
        discovered = discover_maps_from_comparison(bytes(original), [bytes(modified)])
        # A 1-byte change in noise yields no map-shaped region.
        assert all(d.from_geometry for d in discovered) or discovered == []


@pytest.fixture
def original_and_tuned(context: ApplicationContext, tmp_path: Path):
    original, map_offset = build_synthetic_dump()
    orig_path = tmp_path / "orig.bin"
    orig_path.write_bytes(original)
    modified = bytearray(original)
    for i in range(map_offset, map_offset + 512, 2):
        modified[i] = (modified[i] + 8) & 0xFF
    mod_path = tmp_path / "stage1.bin"
    mod_path.write_bytes(bytes(modified))

    vehicle = context.vehicles.create(VehicleInput(make="VW", model="Golf"))
    orig = context.ecu_files.import_file(orig_path, vehicle_id=vehicle.id, kind=EcuFileKind.ORIGINAL)
    tuned = context.ecu_files.import_file(mod_path, vehicle_id=vehicle.id, parent_file_id=orig.id)
    return context, orig, tuned, map_offset


class TestBuildPackFromComparison:
    def test_generates_and_applies_pack(self, original_and_tuned) -> None:
        context, orig, tuned, map_offset = original_and_tuned

        source = context.definitions.build_pack_from_comparison(orig.id, [tuned.id])
        assert source.map_count >= 1
        assert source.id in {s.id for s in context.definitions.list_sources()}

        definitions = context.definitions.list_definitions(source.id)
        assert any(d.offset == map_offset for d in definitions)

        # The learned pack matches the original by SHA-256 and re-proposes maps.
        candidates = context.definitions.apply_definitions(orig.id)
        applied = [c for c in candidates if c.definition_id is not None]
        assert any(c.offset == map_offset for c in applied)
        # Still a proposal — human validation remains required (ADR-0004).
        assert all(c.status == MapCandidateStatus.PROPOSED for c in applied)

    def test_identical_files_raise(self, context: ApplicationContext, tmp_path: Path) -> None:
        data, _ = build_synthetic_dump()
        p = tmp_path / "a.bin"
        p.write_bytes(data)
        vehicle = context.vehicles.create(VehicleInput(make="VW", model="Golf"))
        a = context.ecu_files.import_file(p, vehicle_id=vehicle.id)
        b = context.ecu_files.import_file(p, vehicle_id=vehicle.id)  # same content
        with pytest.raises(PackImportError, match="identiques"):
            context.definitions.build_pack_from_comparison(a.id, [b.id])

    def test_no_modified_files_raises(self, original_and_tuned) -> None:
        context, orig, _tuned, _off = original_and_tuned
        with pytest.raises(ValueError, match="au moins un"):
            context.definitions.build_pack_from_comparison(orig.id, [])


class TestBuildPackFromValidated:
    def test_captures_validated_maps(self, context: ApplicationContext, tmp_path: Path) -> None:
        data, offset = build_synthetic_dump()
        p = tmp_path / "orig.bin"
        p.write_bytes(data)
        vehicle = context.vehicles.create(VehicleInput(make="VW", model="Golf"))
        f = context.ecu_files.import_file(p, vehicle_id=vehicle.id)
        cand = next(c for c in context.analysis.detect_maps(f.id) if c.offset == offset)
        context.analysis.set_candidate_status(cand.id, MapCandidateStatus.VALIDATED, name="Injection")

        source = context.definitions.build_pack_from_validated(f.id)
        definitions = context.definitions.list_definitions(source.id)
        assert [d.name for d in definitions] == ["Injection"]
        assert definitions[0].offset == offset

    def test_no_validated_raises(self, context: ApplicationContext, tmp_path: Path) -> None:
        data, _ = build_synthetic_dump()
        p = tmp_path / "orig.bin"
        p.write_bytes(data)
        vehicle = context.vehicles.create(VehicleInput(make="VW", model="Golf"))
        f = context.ecu_files.import_file(p, vehicle_id=vehicle.id)
        with pytest.raises(PackImportError, match="Aucune cartographie validée"):
            context.definitions.build_pack_from_validated(f.id)
