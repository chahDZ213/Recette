"""Heuristic calibration-map detection.

Real ECU calibration maps share a recognisable memory layout: a strictly
monotonic axis (RPM, load, temperature breakpoints) immediately followed by a
rectangular block of smoothly varying values. This module scans a binary for
that pattern and returns *candidates* — never facts (ADR-0004): every
candidate carries a confidence in [0, MAX_CONFIDENCE] and a human-readable
rationale, and requires explicit human validation in the UI before anything
downstream treats it as a map.

The detector is deliberately conservative: confidence is capped below 1.0
because without a definition file a heuristic can never be certain, and
constant/erased regions (0xFF padding) are rejected outright.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: A heuristic can never prove a map; the cap enforces ADR-0004 honesty.
MAX_CONFIDENCE = 0.85

_AXIS_MIN = 8
_AXIS_MAX = 32
_ROW_CANDIDATES = (8, 10, 12, 16, 20)
_MAX_RESULTS = 60


@dataclass(frozen=True, slots=True)
class MapCandidate:
    """A region that *looks like* an axis followed by a 2D calibration table.

    ``offset`` addresses the data block (the axis sits just before it).
    """

    offset: int
    rows: int
    cols: int
    element_size: int  # bytes per element: 1 or 2
    endianness: str  # "le" | "be" ("" for 8-bit)
    confidence: float
    rationale: str

    @property
    def byte_length(self) -> int:
        return self.rows * self.cols * self.element_size

    @property
    def end(self) -> int:
        return self.offset + self.byte_length


def _views(data: bytes) -> list[tuple[np.ndarray, int, str]]:
    """Interpretations of the buffer to scan: (array, element_size, endianness)."""
    raw = np.frombuffer(data, dtype=np.uint8)
    views: list[tuple[np.ndarray, int, str]] = [(raw.astype(np.int64), 1, "")]
    even = len(data) - (len(data) % 2)
    if even >= 2:
        views.append(
            (np.frombuffer(data[:even], dtype="<u2").astype(np.int64), 2, "le")
        )
        views.append(
            (np.frombuffer(data[:even], dtype=">u2").astype(np.int64), 2, "be")
        )
    return views


def _strict_runs(values: np.ndarray) -> list[tuple[int, int]]:
    """Strictly increasing runs [start, end) of length >= _AXIS_MIN, in element units."""
    if len(values) < _AXIS_MIN:
        return []
    increasing = np.diff(values) > 0
    padded = np.concatenate(([False], increasing, [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    runs = []
    for start, end in zip(edges[::2], edges[1::2], strict=True):
        length = end - start + 1  # diff run of n covers n+1 elements
        if length >= _AXIS_MIN:
            runs.append((int(start), int(start + length)))
    return runs


def _smoothness(block: np.ndarray) -> float | None:
    """Score in [0, 1]: how smoothly values vary along rows AND columns.

    A genuine calibration table is smooth in both directions; a misaligned
    reinterpretation (wrong column count) keeps rows locally smooth but
    scrambles the columns, so weighing both axes rejects wrong geometries.

    Returns None for blocks that cannot be calibration data: constant or
    near-constant content, or blocks dominated by one repeated value —
    the signature of erased-flash padding (0xFF/0x0000) swallowed by an
    over-greedy geometry, which would otherwise look perfectly "smooth".
    """
    value_range = float(block.max() - block.min())
    if value_range == 0.0 or np.unique(block).size < max(4, block.size // 16):
        return None
    _, counts = np.unique(block, return_counts=True)
    if counts.max() > block.size * 0.25:
        return None
    floats = block.astype(np.float64)
    scores = []
    for axis in (1, 0):
        roughness = float(np.abs(np.diff(floats, n=2, axis=axis)).mean()) / (value_range * 0.25)
        scores.append(max(0.0, 1.0 - min(1.0, roughness)))
    return 0.6 * scores[0] + 0.4 * scores[1]


def _axis_length_candidates(run_length: int) -> list[int]:
    """Column counts to try for one monotonic run.

    A run can be longer than the real axis when the table's first row keeps
    increasing past the axis (common: both are ascending). Trying the usual
    axis sizes — not just the full run — lets the scoring pick the geometry
    that actually fits the data.
    """
    usual = [length for length in (8, 10, 12, 16, 20, 24, 32) if length <= run_length]
    capped = min(run_length, _AXIS_MAX)
    if capped not in usual:
        usual.append(capped)
    return usual


def detect_maps(data: bytes) -> list[MapCandidate]:
    """Scan a binary and return map candidates sorted by descending confidence."""
    candidates: list[MapCandidate] = []
    for values, element_size, endianness in _views(data):
        for run_start, run_end in _strict_runs(values):
            run_length = run_end - run_start
            # (score, rows, cols, data_start, smooth)
            best: tuple[float, int, int, int, float] | None = None
            for axis_len in _axis_length_candidates(run_length):
                cols = axis_len
                data_start = run_start + axis_len  # block follows the axis
                axis_quality = (axis_len - _AXIS_MIN) / (_AXIS_MAX - _AXIS_MIN)
                for rows in _ROW_CANDIDATES:
                    end = data_start + rows * cols
                    if end > len(values):
                        continue
                    block = values[data_start:end].reshape(rows, cols)
                    smooth = _smoothness(block)
                    if smooth is None or smooth < 0.55:
                        continue
                    score = min(
                        MAX_CONFIDENCE, 0.10 + 0.15 * axis_quality + 0.6 * smooth
                    )
                    # On (near-)equal scores prefer the larger geometry: a
                    # 12-row table scores like its first 8 rows but covers
                    # the real map, which is what the user wants outlined.
                    if (
                        best is None
                        or score > best[0] + 1e-6
                        or (abs(score - best[0]) <= 1e-6 and rows * cols > best[1] * best[2])
                    ):
                        best = (score, rows, cols, data_start, smooth)

            if best is None:
                continue
            score, rows, cols, data_start, smooth = best
            candidates.append(
                MapCandidate(
                    offset=data_start * element_size,
                    rows=rows,
                    cols=cols,
                    element_size=element_size,
                    endianness=endianness,
                    confidence=round(score, 3),
                    rationale=(
                        f"Axe strictement croissant de {cols} valeurs "
                        f"({8 * element_size} bits{' ' + endianness if endianness else ''}) "
                        f"suivi d'un bloc {rows}×{cols} à variation régulière "
                        f"(régularité {smooth:.0%}). Heuristique sans fichier de "
                        "définition : validation humaine requise."
                    ),
                )
            )

    # Overlap suppression: keep the most confident candidate per region.
    candidates.sort(key=lambda c: c.confidence, reverse=True)
    kept: list[MapCandidate] = []
    for candidate in candidates:
        start, end = candidate.offset, candidate.offset + candidate.byte_length
        if any(
            not (end <= k.offset or start >= k.offset + k.byte_length) for k in kept
        ):
            continue
        kept.append(candidate)
        if len(kept) >= _MAX_RESULTS:
            break
    return kept


def decode_block(
    data: bytes, offset: int, rows: int, cols: int, element_size: int, endianness: str
) -> np.ndarray:
    """Decode a candidate's data block into a rows×cols array of integers."""
    count = rows * cols
    end = offset + count * element_size
    if offset < 0 or end > len(data):
        raise ValueError("Block exceeds file bounds")
    if element_size == 1:
        flat = np.frombuffer(data[offset:end], dtype=np.uint8)
    elif element_size == 2:
        dtype = "<u2" if endianness == "le" else ">u2"
        flat = np.frombuffer(data[offset:end], dtype=dtype)
    else:
        raise ValueError(f"Unsupported element size: {element_size}")
    return flat.reshape(rows, cols).astype(np.int64)


def encode_block(
    data: bytes,
    offset: int,
    values: np.ndarray,
    element_size: int,
    endianness: str,
) -> bytes:
    """Return a copy of ``data`` with ``values`` written into the block at
    ``offset``. The original bytes are never mutated (immutability, ADR-0003):
    a new bytes object is returned for a fresh, separate blob.

    Values are clamped to the storage type's range (a tuner asking for more
    than the cell can hold gets the max, not an overflow), which keeps the
    write safe on real ECU dumps.
    """
    rows, cols = values.shape
    count = rows * cols
    end = offset + count * element_size
    if offset < 0 or end > len(data):
        raise ValueError("Block exceeds file bounds")
    if element_size == 1:
        dtype = np.dtype(np.uint8)
        max_value = 0xFF
    elif element_size == 2:
        dtype = np.dtype("<u2" if endianness == "le" else ">u2")
        max_value = 0xFFFF
    else:
        raise ValueError(f"Unsupported element size: {element_size}")

    clamped = np.clip(np.rint(values), 0, max_value).astype(dtype)
    buffer = bytearray(data)
    buffer[offset:end] = clamped.reshape(-1).tobytes()
    return bytes(buffer)
