"""Tests for map editing: encode_block, edit_map, scale_map, export."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from tests.test_mapdetect import build_synthetic_dump

from calforge.analysis.mapdetect import decode_block, encode_block
from calforge.app import ApplicationContext
from calforge.data.models import EcuFileKind, MapCandidateStatus
from calforge.services.dto import VehicleInput


class TestEncodeBlock:
    def test_roundtrip(self) -> None:
        data = bytearray(0x100)
        values = np.arange(16, dtype=np.int64).reshape(4, 4) * 100
        edited = encode_block(bytes(data), 0x10, values, element_size=2, endianness="le")
        decoded = decode_block(edited, 0x10, 4, 4, 2, "le")
        assert np.array_equal(decoded, values)

    def test_does_not_mutate_input(self) -> None:
        original = bytes(0x100)
        values = np.ones((4, 4), dtype=np.int64) * 500
        edited = encode_block(original, 0x10, values, element_size=2, endianness="le")
        assert original == bytes(0x100)  # untouched
        assert edited != original

    def test_clamps_overflow(self) -> None:
        data = bytes(0x20)
        values = np.array([[70000, -5], [0, 65535]], dtype=np.int64)  # 2x2 uint16
        edited = encode_block(data, 0, values, element_size=2, endianness="le")
        decoded = decode_block(edited, 0, 2, 2, 2, "le")
        assert decoded[0, 0] == 65535  # clamped to max
        assert decoded[0, 1] == 0  # clamped to min
        assert decoded[1, 1] == 65535

    def test_out_of_bounds_rejected(self) -> None:
        with pytest.raises(ValueError):
            encode_block(bytes(8), 4, np.zeros((2, 2), dtype=np.int64), 2, "le")


@pytest.fixture
def validated_map(context: ApplicationContext, tmp_path: Path):
    data, offset = build_synthetic_dump()
    path = tmp_path / "orig.bin"
    path.write_bytes(data)
    vehicle = context.vehicles.create(VehicleInput(make="VW", model="Golf"))
    file = context.ecu_files.import_file(path, vehicle_id=vehicle.id, kind=EcuFileKind.ORIGINAL)
    candidates = context.analysis.detect_maps(file.id)
    target = next(c for c in candidates if c.offset == offset)
    context.analysis.set_candidate_status(target.id, MapCandidateStatus.VALIDATED, name="Injection")
    return vehicle, file, target


class TestEditMap:
    def test_edit_creates_new_file_and_preserves_original(
        self, context: ApplicationContext, validated_map
    ) -> None:
        vehicle, file, candidate = validated_map
        original_sha = file.sha256
        original_bytes = context.ecu_files.read_content(file.id)

        values = context.analysis.read_map_values(candidate.id)
        new_values = values + 50  # bump every cell

        new_file = context.analysis.edit_map(candidate.id, new_values)

        # New file is a modified derivative of the original.
        assert new_file.id != file.id
        assert new_file.kind == EcuFileKind.MODIFIED
        assert new_file.parent_file_id == file.id
        assert new_file.vehicle_id == vehicle.id
        assert new_file.sha256 != original_sha

        # The ORIGINAL is byte-for-byte untouched (immutability).
        assert context.ecu_files.read_content(file.id) == original_bytes

        # The new file carries the edited values at the map offset.
        edited = context.ecu_files.read_content(new_file.id)
        from calforge.analysis.mapdetect import decode_block
        decoded = decode_block(
            edited, candidate.offset, candidate.rows, candidate.cols,
            candidate.element_size, candidate.endianness,
        )
        assert np.array_equal(decoded, new_values)
        # Bytes outside the map region are unchanged.
        assert edited[: candidate.offset] == original_bytes[: candidate.offset]

    def test_edit_rejects_wrong_shape(
        self, context: ApplicationContext, validated_map
    ) -> None:
        _v, _f, candidate = validated_map
        with pytest.raises(ValueError, match="incompatibles"):
            context.analysis.edit_map(candidate.id, np.zeros((3, 3)))

    def test_scale_map_percent(self, context: ApplicationContext, validated_map) -> None:
        _v, _f, candidate = validated_map
        before = context.analysis.read_map_values(candidate.id)

        new_file = context.analysis.scale_map(candidate.id, 10.0)  # +10%

        edited = context.ecu_files.read_content(new_file.id)
        from calforge.analysis.mapdetect import decode_block
        after = decode_block(
            edited, candidate.offset, candidate.rows, candidate.cols,
            candidate.element_size, candidate.endianness,
        )
        expected = np.rint(before.astype(float) * 1.10).astype(np.int64)
        assert np.array_equal(after, np.clip(expected, 0, 65535))

    def test_derived_filename(self, context: ApplicationContext, validated_map) -> None:
        _v, file, candidate = validated_map
        new_file = context.analysis.edit_map(
            candidate.id, context.analysis.read_map_values(candidate.id) + 1
        )
        assert new_file.original_filename == "orig_modifie.bin"

    def test_export_to_disk(
        self, context: ApplicationContext, validated_map, tmp_path
    ) -> None:
        _v, file, candidate = validated_map
        new_file = context.analysis.scale_map(candidate.id, 5.0)
        target = context.ecu_files.export_to(new_file.id, tmp_path / "out" / "tuned.bin")
        assert target.read_bytes() == context.ecu_files.read_content(new_file.id)
