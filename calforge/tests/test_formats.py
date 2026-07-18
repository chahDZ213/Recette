from __future__ import annotations

from pathlib import Path

import pytest

from calforge.formats.base import Hypothesis, run_identification
from calforge.formats.generic import GenericBinaryIdentifier, shannon_entropy


def test_entropy_bounds() -> None:
    assert shannon_entropy(b"") == 0.0
    assert shannon_entropy(b"\x00" * 1000) == 0.0
    assert shannon_entropy(bytes(range(256)) * 4) == pytest.approx(8.0)


def test_generic_identifier_reports_only_measured_facts(tmp_path: Path) -> None:
    path = tmp_path / "dump.bin"
    data = b"\x12\x34" * 100
    path.write_bytes(data)

    report = GenericBinaryIdentifier().identify(path, data)

    assert report.facts["size_bytes"] == 200
    assert report.facts["extension"] == ".bin"
    # Facts must never contain guesses about vehicle/ECU identity.
    assert "ecu_type" not in report.facts


def test_flash_dump_hypothesis_for_power_of_two_size(tmp_path: Path) -> None:
    path = tmp_path / "dump.bin"
    data = b"\xff" * (1 << 19)  # 512 KiB of erased flash
    path.write_bytes(data)

    report = GenericBinaryIdentifier().identify(path, data)

    statements = [h.statement for h in report.hypotheses]
    assert any("flash" in s.lower() for s in statements)
    for hypothesis in report.hypotheses:
        assert 0.0 <= hypothesis.confidence <= 1.0
        assert hypothesis.rationale  # a hypothesis without rationale is invalid


def test_hypothesis_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError):
        Hypothesis(statement="x", confidence=1.5, rationale="y")


def test_pipeline_prefers_most_specific_identifier(tmp_path: Path) -> None:
    class SpecificIdentifier:
        name = "specific"
        specificity = 10

        def identify(self, path, data):
            from calforge.formats.base import IdentificationReport

            return IdentificationReport(format_name=self.name)

    path = tmp_path / "x.bin"
    path.write_bytes(b"data")
    report = run_identification(
        [GenericBinaryIdentifier(), SpecificIdentifier()], path, b"data"
    )
    assert report.format_name == "specific"
