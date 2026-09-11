"""Binary diff engine.

Compares two binaries byte-per-byte using NumPy (vectorised, handles multi-MB
ECU dumps in milliseconds) and reports contiguous difference regions. Nearby
regions separated by fewer than ``merge_gap`` identical bytes are merged: a
recalibrated map rarely changes every cell, and fragmenting it into dozens of
micro-regions would drown the user. The raw changed-byte count is preserved
separately so merging never inflates the reported change volume.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class DiffRegion:
    """A contiguous region [offset, offset + length) that differs."""

    offset: int
    length: int
    changed_bytes: int

    @property
    def end(self) -> int:
        return self.offset + self.length


@dataclass(frozen=True, slots=True)
class DiffResult:
    size_a: int
    size_b: int
    regions: tuple[DiffRegion, ...]
    total_changed_bytes: int

    @property
    def identical(self) -> bool:
        return self.size_a == self.size_b and not self.regions


def diff_bytes(a: bytes, b: bytes, *, merge_gap: int = 8) -> DiffResult:
    """Diff two byte strings.

    If sizes differ, the common prefix is compared and the tail of the longer
    file is reported as one trailing region — ECU dumps of different sizes are
    almost always different memory ranges, and pretending to align them would
    fabricate structure that is not there.
    """
    if merge_gap < 0:
        raise ValueError("merge_gap must be >= 0")
    common = min(len(a), len(b))
    arr_a = np.frombuffer(a, dtype=np.uint8, count=common)
    arr_b = np.frombuffer(b, dtype=np.uint8, count=common)
    mismatch = arr_a != arr_b

    regions: list[DiffRegion] = []
    total_changed = int(np.count_nonzero(mismatch))

    if total_changed:
        # Boundaries of runs of mismatching bytes.
        padded = np.concatenate(([False], mismatch, [False]))
        edges = np.flatnonzero(padded[1:] != padded[:-1])
        starts, ends = edges[::2], edges[1::2]

        merged: list[tuple[int, int, int]] = []  # (start, end, changed)
        for start, end in zip(starts.tolist(), ends.tolist(), strict=True):
            changed = int(np.count_nonzero(mismatch[start:end]))
            if merged and start - merged[-1][1] <= merge_gap:
                prev_start, _prev_end, prev_changed = merged[-1]
                merged[-1] = (prev_start, end, prev_changed + changed)
            else:
                merged.append((start, end, changed))
        regions = [
            DiffRegion(offset=start, length=end - start, changed_bytes=changed)
            for start, end, changed in merged
        ]

    if len(a) != len(b):
        tail_length = abs(len(a) - len(b))
        regions.append(
            DiffRegion(offset=common, length=tail_length, changed_bytes=tail_length)
        )
        total_changed += tail_length

    return DiffResult(
        size_a=len(a),
        size_b=len(b),
        regions=tuple(regions),
        total_changed_bytes=total_changed,
    )
