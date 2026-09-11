"""Format identification contract.

The cardinal rule (ADR-0004): **identification never invents data**.
An ``IdentificationReport`` separates

- ``facts``       — information proven from the file content alone
                    (size, hashes, measured statistics). Always trustworthy.
- ``hypotheses``  — scored guesses (e.g. "looks like a full flash dump"),
                    each carrying a confidence in [0, 1] and a human-readable
                    rationale, and requiring human validation before any
                    downstream feature treats it as true.

Identifiers return ``None`` when the file is not theirs to describe; the
pipeline keeps the report whose matched identifier is the most specific
(highest ``specificity``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Hypothesis:
    statement: str
    confidence: float  # 0.0 .. 1.0, never displayed without the rationale
    rationale: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be within [0, 1], got {self.confidence}")


@dataclass(frozen=True, slots=True)
class IdentificationReport:
    format_name: str
    facts: dict[str, object] = field(default_factory=dict)
    hypotheses: tuple[Hypothesis, ...] = ()


@runtime_checkable
class FormatIdentifier(Protocol):
    """Extension point for ECU file formats."""

    name: str
    #: Higher wins when several identifiers match. Generic fallbacks use 0.
    specificity: int

    def identify(self, path: Path, data: bytes) -> IdentificationReport | None:
        """Return a report if this identifier recognises the file, else None."""
        ...


def run_identification(
    identifiers: list[FormatIdentifier], path: Path, data: bytes
) -> IdentificationReport:
    """Run all identifiers and return the most specific successful report.

    Always returns a report: the pipeline requires at least one generic
    fallback identifier (registered as a built-in plugin).
    """
    best: tuple[int, IdentificationReport] | None = None
    for identifier in identifiers:
        report = identifier.identify(path, data)
        if report is None:
            continue
        if best is None or identifier.specificity > best[0]:
            best = (identifier.specificity, report)
    if best is None:
        raise RuntimeError(
            "No format identifier matched; the generic fallback should always match."
        )
    return best[1]
