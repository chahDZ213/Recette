"""Tests for v0.4: pack import/export, matching, definition application."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.test_mapdetect import build_synthetic_dump

from calforge.app import ApplicationContext
from calforge.data.models import MapCandidateStatus, MatcherKind
from calforge.services.definitions import PackImportError
from calforge.services.dto import VehicleInput


def write_pack(path: Path, *, name: str, matchers: list[dict], maps: list[dict] | None = None) -> Path:
    pack = {
        "format": "calforge-pack/1",
        "name": name,
        "description": "Pack de test",
        "matchers": matchers,
        "maps": maps
        or [
            {
                "name": "Injection — charge/régime",
                "category": "injection",
                "offset": "0x420",
                "rows": 16,
                "cols": 16,
                "element_size": 2,
                "endianness": "le",
                "factor": 0.1,
                "value_offset": 0.0,
                "unit": "mg/cp",
            }
        ],
    }
    path.write_text(json.dumps(pack), encoding="utf-8")
    return path


@pytest.fixture
def imported_dump(context: ApplicationContext, tmp_path: Path):
    data, map_offset = build_synthetic_dump()  # map data block at 0x420
    path = tmp_path / "dump.bin"
    path.write_bytes(data)
    vehicle = context.vehicles.create(VehicleInput(make="VW", model="Golf"))
    dto = context.ecu_files.import_file(path, vehicle_id=vehicle.id)
    assert map_offset == 0x420  # keep the pack fixture in sync with the dump
    return dto


class TestPackImportExport:
    def test_import_and_roundtrip(self, context: ApplicationContext, tmp_path: Path, imported_dump) -> None:
        pack_path = write_pack(
            tmp_path / "test.calpack.json",
            name="Pack Golf",
            matchers=[{"kind": "sha256", "sha256": imported_dump.sha256}],
        )

        source = context.definitions.import_pack(pack_path)
        assert source.map_count == 1
        assert [s.name for s in context.definitions.list_sources()] == ["Pack Golf"]

        definitions = context.definitions.list_definitions(source.id)
        assert definitions[0].offset == 0x420
        assert definitions[0].factor == pytest.approx(0.1)

        exported = context.definitions.export_pack(source.id, tmp_path / "out.calpack.json")
        reparsed = json.loads(exported.read_text(encoding="utf-8"))
        assert reparsed["name"] == "Pack Golf"
        assert reparsed["maps"][0]["offset"] == 0x420
        assert reparsed["matchers"][0]["sha256"] == imported_dump.sha256

    def test_duplicate_name_rejected(self, context: ApplicationContext, tmp_path: Path) -> None:
        pack_path = write_pack(tmp_path / "p.calpack.json", name="Doublon", matchers=[])
        context.definitions.import_pack(pack_path)
        with pytest.raises(PackImportError, match="existe déjà"):
            context.definitions.import_pack(pack_path)

    def test_invalid_json_rejected(self, context: ApplicationContext, tmp_path: Path) -> None:
        bad = tmp_path / "bad.calpack.json"
        bad.write_text("{not json", encoding="utf-8")
        with pytest.raises(PackImportError):
            context.definitions.import_pack(bad)

    def test_invalid_schema_rejected(self, context: ApplicationContext, tmp_path: Path) -> None:
        bad = tmp_path / "bad2.calpack.json"
        bad.write_text(json.dumps({"format": "calforge-pack/1", "name": "X", "maps": []}))
        with pytest.raises(PackImportError):
            context.definitions.import_pack(bad)


class TestMatching:
    def test_sha256_match_wins_over_size(
        self, context: ApplicationContext, tmp_path: Path, imported_dump
    ) -> None:
        write_pack(
            tmp_path / "a.calpack.json",
            name="Pack exact",
            matchers=[{"kind": "sha256", "sha256": imported_dump.sha256}],
        )
        write_pack(
            tmp_path / "b.calpack.json",
            name="Pack taille",
            matchers=[{"kind": "size", "size": imported_dump.size_bytes}],
        )
        write_pack(
            tmp_path / "c.calpack.json",
            name="Pack étranger",
            matchers=[{"kind": "sha256", "sha256": "0" * 64}],
        )
        for name in ("a", "b", "c"):
            context.definitions.import_pack(tmp_path / f"{name}.calpack.json")

        matches = context.definitions.match_sources_for_file(imported_dump.id)
        assert [(m.source.name, m.matched_by) for m in matches] == [
            ("Pack exact", MatcherKind.SHA256),
            ("Pack taille", MatcherKind.SIZE),
        ]

    def test_signature_match_reads_content(
        self, context: ApplicationContext, tmp_path: Path, imported_dump
    ) -> None:
        data = context.ecu_files.read_content(imported_dump.id)
        signature = data[0x400:0x408].hex()
        write_pack(
            tmp_path / "sig.calpack.json",
            name="Pack signature",
            matchers=[{"kind": "signature", "offset": "0x400", "hex": signature}],
        )
        context.definitions.import_pack(tmp_path / "sig.calpack.json")

        matches = context.definitions.match_sources_for_file(imported_dump.id)
        assert [(m.source.name, m.matched_by) for m in matches] == [
            ("Pack signature", MatcherKind.SIGNATURE)
        ]


class TestApplication:
    def test_apply_creates_named_high_confidence_candidates(
        self, context: ApplicationContext, tmp_path: Path, imported_dump
    ) -> None:
        write_pack(
            tmp_path / "p.calpack.json",
            name="Pack Golf",
            matchers=[{"kind": "sha256", "sha256": imported_dump.sha256}],
        )
        context.definitions.import_pack(tmp_path / "p.calpack.json")

        candidates = context.definitions.apply_definitions(imported_dump.id)
        applied = [c for c in candidates if c.definition_id is not None]

        assert len(applied) == 1
        candidate = applied[0]
        assert candidate.offset == 0x420
        assert candidate.name == "Injection — charge/régime"
        assert candidate.confidence == pytest.approx(0.95)
        assert candidate.status == MapCandidateStatus.PROPOSED  # human still validates
        assert "Pack Golf" in candidate.rationale

    def test_apply_is_idempotent(
        self, context: ApplicationContext, tmp_path: Path, imported_dump
    ) -> None:
        write_pack(
            tmp_path / "p.calpack.json",
            name="Pack Golf",
            matchers=[{"kind": "sha256", "sha256": imported_dump.sha256}],
        )
        context.definitions.import_pack(tmp_path / "p.calpack.json")

        first = context.definitions.apply_definitions(imported_dump.id)
        second = context.definitions.apply_definitions(imported_dump.id)
        assert len([c for c in second if c.definition_id]) == len(
            [c for c in first if c.definition_id]
        )

    def test_apply_respects_human_decisions(
        self, context: ApplicationContext, tmp_path: Path, imported_dump
    ) -> None:
        # The heuristic finds the map; the human validates it…
        detected = context.analysis.detect_maps(imported_dump.id)
        target = next(c for c in detected if c.offset == 0x420)
        context.analysis.set_candidate_status(
            target.id, MapCandidateStatus.VALIDATED, name="Ma carte"
        )

        # …then a pack covering the same region is applied: it must not
        # override or duplicate the validated candidate.
        write_pack(
            tmp_path / "p.calpack.json",
            name="Pack Golf",
            matchers=[{"kind": "sha256", "sha256": imported_dump.sha256}],
        )
        context.definitions.import_pack(tmp_path / "p.calpack.json")
        after = context.definitions.apply_definitions(imported_dump.id)

        validated = [c for c in after if c.status == MapCandidateStatus.VALIDATED]
        assert [c.name for c in validated] == ["Ma carte"]
        for candidate in after:
            if candidate.id == target.id:
                continue
            assert candidate.end <= target.offset or candidate.offset >= target.end

    def test_no_match_no_candidates(self, context: ApplicationContext, tmp_path: Path, imported_dump) -> None:
        write_pack(
            tmp_path / "p.calpack.json",
            name="Pack étranger",
            matchers=[{"kind": "sha256", "sha256": "f" * 64}],
        )
        context.definitions.import_pack(tmp_path / "p.calpack.json")
        candidates = context.definitions.apply_definitions(imported_dump.id)
        assert [c for c in candidates if c.definition_id is not None] == []
