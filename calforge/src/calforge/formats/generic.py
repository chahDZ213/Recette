"""Generic binary identifier — the always-matching fallback.

Reports only measured facts (size, entropy, fill ratios) plus carefully
hedged hypotheses derived from well-known ECU dump characteristics
(power-of-two sizes, high 0xFF fill in erased flash sectors).
"""

from __future__ import annotations

from pathlib import Path

from calforge.analysis.stats import shannon_entropy
from calforge.formats.base import Hypothesis, IdentificationReport

__all__ = ["GenericBinaryIdentifier", "shannon_entropy"]

# Flash memory sizes commonly seen in ECU full dumps (256 KiB .. 32 MiB).
_COMMON_FLASH_SIZES = {1 << n for n in range(18, 26)}


class GenericBinaryIdentifier:
    name = "generic-binary"
    specificity = 0

    def identify(self, path: Path, data: bytes) -> IdentificationReport:
        size = len(data)
        entropy = shannon_entropy(data)
        ff_ratio = data.count(0xFF) / size if size else 0.0
        zero_ratio = data.count(0x00) / size if size else 0.0

        facts: dict[str, object] = {
            "size_bytes": size,
            "entropy_bits_per_byte": round(entropy, 3),
            "ratio_0xFF": round(ff_ratio, 4),
            "ratio_0x00": round(zero_ratio, 4),
            "extension": path.suffix.lower(),
        }

        hypotheses: list[Hypothesis] = []
        if size in _COMMON_FLASH_SIZES:
            hypotheses.append(
                Hypothesis(
                    statement="Could be a full flash memory dump",
                    confidence=0.5,
                    rationale=(
                        f"File size ({size} bytes) is exactly a power of two "
                        "commonly matching ECU flash chip capacities."
                    ),
                )
            )
        if ff_ratio > 0.25:
            hypotheses.append(
                Hypothesis(
                    statement="Contains erased/padded flash sectors",
                    confidence=min(0.9, ff_ratio + 0.3),
                    rationale=(
                        f"{ff_ratio:.0%} of the file is 0xFF, the erased state "
                        "of NOR flash memory."
                    ),
                )
            )
        if entropy > 7.9:
            hypotheses.append(
                Hypothesis(
                    statement="Data may be encrypted or compressed",
                    confidence=0.6,
                    rationale=(
                        f"Entropy of {entropy:.2f} bits/byte is close to the "
                        "theoretical maximum, unusual for plain calibration data."
                    ),
                )
            )

        return IdentificationReport(
            format_name=self.name, facts=facts, hypotheses=tuple(hypotheses)
        )
