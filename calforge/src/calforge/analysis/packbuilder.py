"""Differential map-pack builder — learning maps from real evidence.

The most reliable way (short of a DAMOS/A2L) to know *where the maps are* in a
given ECU is the technique every tuner uses by hand: take an original and a
known-tuned file for the same ECU and see which bytes changed — those regions
are the maps that were actually touched. This module automates exactly that.

It combines two independent signals so a result is trustworthy:

1. **What changed** — the byte regions that differ between the original and one
   or more modified files (real evidence a human editor altered them).
2. **What looks like a map** — the heuristic detector's geometry
   (:mod:`calforge.analysis.mapdetect`): a monotonic axis followed by a smooth
   table.

A region backed by *both* signals is a strong map candidate. Regions that
changed but match no detected geometry are still reported (best-effort, lower
confidence) so nothing real is silently dropped — but they are clearly marked,
never presented as certain (ADR-0004).
"""

from __future__ import annotations

from dataclasses import dataclass

from calforge.analysis.diff import diff_bytes
from calforge.analysis.mapdetect import MapCandidate, detect_maps


@dataclass(frozen=True, slots=True)
class DiscoveredMap:
    """A map region learned from comparison, with the evidence behind it."""

    offset: int
    rows: int
    cols: int
    element_size: int
    endianness: str
    confidence: float
    changed_bytes: int
    from_geometry: bool  # True: matches a detected map shape; False: raw region

    @property
    def byte_length(self) -> int:
        return self.rows * self.cols * self.element_size

    @property
    def end(self) -> int:
        return self.offset + self.byte_length


def _changed_ranges(original: bytes, modified_files: list[bytes]) -> list[tuple[int, int]]:
    """Merged (start, end) byte ranges that differ in ANY modified file."""
    ranges: list[tuple[int, int]] = []
    for modified in modified_files:
        result = diff_bytes(original, modified)
        for region in result.regions:
            ranges.append((region.offset, region.end))
    if not ranges:
        return []
    ranges.sort()
    merged = [ranges[0]]
    for start, end in ranges[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:  # overlapping/adjacent -> merge
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return not (a_end <= b_start or a_start >= b_end)


def discover_maps_from_comparison(
    original: bytes, modified_files: list[bytes]
) -> list[DiscoveredMap]:
    """Learn map regions from an original and one or more modified files.

    Returns discovered maps sorted by descending confidence. Geometry-backed
    regions (changed AND map-shaped) rank highest; changed-only regions follow.
    """
    changed = _changed_ranges(original, modified_files)
    if not changed:
        return []

    detected: list[MapCandidate] = detect_maps(original)
    discovered: list[DiscoveredMap] = []
    covered: list[tuple[int, int]] = []

    # 1. Detected map shapes that were actually touched — strongest evidence.
    for candidate in detected:
        changed_here = sum(
            min(candidate.end, ce) - max(candidate.offset, cs)
            for cs, ce in changed
            if _overlaps(candidate.offset, candidate.end, cs, ce)
        )
        if changed_here <= 0:
            continue
        # Confidence: the heuristic score, lifted because a real edit confirms it.
        confidence = min(0.9, candidate.confidence + 0.15)
        discovered.append(
            DiscoveredMap(
                offset=candidate.offset,
                rows=candidate.rows,
                cols=candidate.cols,
                element_size=candidate.element_size,
                endianness=candidate.endianness,
                confidence=round(confidence, 3),
                changed_bytes=int(changed_here),
                from_geometry=True,
            )
        )
        covered.append((candidate.offset, candidate.end))

    # 2. Changed regions with no detected geometry — best-effort, low confidence.
    for start, end in changed:
        if any(_overlaps(start, end, cs, ce) for cs, ce in covered):
            continue
        length = end - start
        if length < 8:  # too small to be a table; likely a checksum/counter tweak
            continue
        element_size = 2 if length % 2 == 0 else 1
        cols = _guess_columns(length // element_size)
        rows = max(1, (length // element_size) // cols)
        discovered.append(
            DiscoveredMap(
                offset=start,
                rows=rows,
                cols=cols,
                element_size=element_size,
                endianness="le",
                confidence=0.4,
                changed_bytes=length,
                from_geometry=False,
            )
        )

    discovered.sort(key=lambda m: m.confidence, reverse=True)
    return discovered


def _guess_columns(element_count: int) -> int:
    """Pick a plausible column count for a raw changed region.

    Prefers common ECU axis widths that divide the element count evenly, else
    falls back to the whole region as a single row."""
    for width in (16, 12, 10, 8, 20, 24, 32):
        if element_count % width == 0:
            return width
    return element_count
