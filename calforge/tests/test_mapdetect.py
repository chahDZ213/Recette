"""Map detector tests: planted maps must be found, noise must stay clean."""

from __future__ import annotations

import numpy as np
import pytest

from calforge.analysis.mapdetect import MAX_CONFIDENCE, decode_block, detect_maps
from calforge.analysis.stats import block_entropy, byte_histogram, shannon_entropy


def build_synthetic_dump() -> tuple[bytes, int]:
    """Noise + a realistic planted map (axis + smooth 16×16 uint16 LE table).

    Returns (data, expected data-block offset in bytes).
    """
    rng = np.random.default_rng(42)
    prefix = rng.integers(0, 256, size=1024, dtype=np.uint8).tobytes()

    axis = np.arange(500, 500 + 16 * 120, 120, dtype="<u2")  # strictly increasing
    rows = np.arange(16, dtype=np.float64)[:, None]
    cols = np.arange(16, dtype=np.float64)[None, :]
    table = (1000 + rows * 55 + cols * 30).astype("<u2")  # smooth gradient

    payload = axis.tobytes() + table.tobytes()
    suffix = b"\xff" * 2048
    data = prefix + payload + suffix
    expected_offset = len(prefix) + len(axis.tobytes())
    return data, expected_offset


class TestDetection:
    def test_planted_map_is_found(self) -> None:
        data, expected_offset = build_synthetic_dump()
        candidates = detect_maps(data)

        assert candidates, "the planted map must be detected"
        hits = [c for c in candidates if c.offset == expected_offset]
        assert hits, f"no candidate at 0x{expected_offset:X}: {candidates[:3]}"
        best = hits[0]
        assert best.element_size == 2
        assert best.endianness == "le"
        assert best.cols == 16
        assert best.confidence >= 0.5

    def test_confidence_is_capped_and_rationale_present(self) -> None:
        data, _ = build_synthetic_dump()
        for candidate in detect_maps(data):
            assert 0.0 < candidate.confidence <= MAX_CONFIDENCE
            assert "validation humaine" in candidate.rationale.lower()

    def test_random_noise_yields_no_confident_candidate(self) -> None:
        rng = np.random.default_rng(7)
        noise = rng.integers(0, 256, size=64 * 1024, dtype=np.uint8).tobytes()
        candidates = detect_maps(noise)
        assert all(c.confidence < 0.65 for c in candidates)

    def test_erased_flash_yields_nothing(self) -> None:
        assert detect_maps(b"\xff" * 32768) == []
        assert detect_maps(b"\x00" * 32768) == []

    def test_axis_fused_with_first_row_still_resolved(self) -> None:
        """When the axis and the table's first row ascend continuously (one
        long monotonic run), the detector must still recover the true 16-col
        geometry instead of swallowing padding into an oversized block."""
        rng = np.random.default_rng(11)
        prefix = rng.integers(0, 256, size=512, dtype=np.uint8).tobytes()
        # Axis ends at 2100; table starts at 2400 → the run keeps ascending.
        axis = np.arange(600, 600 + 16 * 100, 100, dtype="<u2")
        rows = np.arange(12, dtype=np.float64)[:, None]
        cols = np.arange(16, dtype=np.float64)[None, :]
        table = (2400 + rows * 40 + cols * 25).astype("<u2")
        data = prefix + axis.tobytes() + table.tobytes() + b"\xff" * 2048
        expected_offset = len(prefix) + len(axis.tobytes())

        candidates = detect_maps(data)
        hits = [c for c in candidates if c.offset == expected_offset and c.cols == 16]
        assert hits, f"expected a 16-col candidate at 0x{expected_offset:X}, got {candidates[:3]}"
        # No candidate may extend into the erased padding.
        table_end = expected_offset + table.nbytes
        for candidate in candidates:
            assert candidate.end <= table_end


class TestDecodeBlock:
    def test_roundtrip_le16(self) -> None:
        data, offset = build_synthetic_dump()
        values = decode_block(data, offset, rows=16, cols=16, element_size=2, endianness="le")
        assert values.shape == (16, 16)
        assert values[0, 0] == 1000
        assert values[1, 0] == 1055
        assert values[0, 1] == 1030

    def test_out_of_bounds_rejected(self) -> None:
        with pytest.raises(ValueError):
            decode_block(b"\x00" * 16, offset=8, rows=4, cols=4, element_size=2, endianness="le")


class TestStats:
    def test_block_entropy_locates_erased_region(self) -> None:
        data = bytes(range(256)) * 16 + b"\xff" * 4096
        blocks = block_entropy(data, block_size=4096)
        assert blocks[0].entropy == pytest.approx(8.0)
        assert blocks[-1].entropy == 0.0

    def test_histogram_counts(self) -> None:
        histogram = byte_histogram(b"\x00\x00\xff")
        assert histogram[0x00] == 2
        assert histogram[0xFF] == 1
        assert histogram.sum() == 3

    def test_entropy_reexport_still_available(self) -> None:
        # formats.generic re-exports shannon_entropy for backward compatibility.
        from calforge.formats.generic import shannon_entropy as reexported

        assert reexported is shannon_entropy
