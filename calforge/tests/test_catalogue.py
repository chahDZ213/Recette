"""Tests for the automatic pack catalogue (folder + URL, no real network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.test_definitions import write_pack
from tests.test_mapdetect import build_synthetic_dump

from calforge.app import ApplicationContext
from calforge.core.config import AppConfig
from calforge.services.catalogue import CatalogueService
from calforge.services.dto import VehicleInput


@pytest.fixture
def imported_file(context: ApplicationContext, tmp_path: Path):
    data, _offset = build_synthetic_dump()
    path = tmp_path / "dump.bin"
    path.write_bytes(data)
    vehicle = context.vehicles.create(VehicleInput(make="VW", model="Golf"))
    return context.ecu_files.import_file(path, vehicle_id=vehicle.id)


class TestFolderCatalogue:
    def test_matching_pack_in_folder_is_fetched(
        self, context: ApplicationContext, imported_file, tmp_path
    ) -> None:
        catalogue_dir = tmp_path / "catalogue"
        catalogue_dir.mkdir()
        write_pack(
            catalogue_dir / "golf.calpack.json",
            name="Pack catalogue",
            matchers=[{"kind": "sha256", "sha256": imported_file.sha256}],
        )
        # A non-matching pack in the same folder must be ignored.
        write_pack(
            catalogue_dir / "other.calpack.json",
            name="Pack étranger",
            matchers=[{"kind": "sha256", "sha256": "0" * 64}],
        )
        config = context.config.packs
        config.catalogue_dirs = [str(catalogue_dir)]

        fetched = context.catalogue.fetch_for_file(imported_file.id)

        assert [s.name for s in fetched] == ["Pack catalogue"]
        assert "Pack catalogue" in {s.name for s in context.definitions.list_sources()}

    def test_size_match_in_folder(
        self, context: ApplicationContext, imported_file, tmp_path
    ) -> None:
        catalogue_dir = tmp_path / "cat"
        catalogue_dir.mkdir()
        write_pack(
            catalogue_dir / "bysize.calpack.json",
            name="Pack par taille",
            matchers=[{"kind": "size", "size": imported_file.size_bytes}],
        )
        context.config.packs.catalogue_dirs = [str(catalogue_dir)]
        fetched = context.catalogue.fetch_for_file(imported_file.id)
        assert [s.name for s in fetched] == ["Pack par taille"]

    def test_invalid_pack_file_is_skipped(
        self, context: ApplicationContext, imported_file, tmp_path
    ) -> None:
        catalogue_dir = tmp_path / "cat"
        catalogue_dir.mkdir()
        (catalogue_dir / "broken.calpack.json").write_text("{not json", encoding="utf-8")
        context.config.packs.catalogue_dirs = [str(catalogue_dir)]
        assert context.catalogue.fetch_for_file(imported_file.id) == []

    def test_no_sources_makes_no_calls(
        self, context: ApplicationContext, imported_file
    ) -> None:
        assert not context.catalogue.enabled
        assert context.catalogue.fetch_for_file(imported_file.id) == []


class TestUrlCatalogue:
    def test_url_fetch_by_hash_with_fake_fetcher(self, app_config: AppConfig, tmp_path) -> None:
        # A fake fetcher returns a pack only for the exact hash URL — no network.
        app_config.packs.catalogue_urls = ["https://packs.example/catalogue"]
        ctx = ApplicationContext(config=app_config)
        try:
            data, _ = build_synthetic_dump()
            p = tmp_path / "d.bin"
            p.write_bytes(data)
            vehicle = ctx.vehicles.create(VehicleInput(make="VW", model="Golf"))
            file = ctx.ecu_files.import_file(p, vehicle_id=vehicle.id)

            expected_url = f"https://packs.example/catalogue/{file.sha256}.calpack.json"
            calls: list[str] = []

            def fake_fetch(url: str, timeout: float) -> bytes | None:
                calls.append(url)
                if url != expected_url:
                    return None
                pack = {
                    "format": "calforge-pack/1",
                    "name": "Pack en ligne",
                    "matchers": [{"kind": "sha256", "sha256": file.sha256}],
                    "maps": [
                        {
                            "name": "Carte", "category": "x", "offset": "0x420",
                            "rows": 16, "cols": 16, "element_size": 2, "endianness": "le",
                            "factor": 1.0, "value_offset": 0.0, "unit": "",
                        }
                    ],
                }
                return json.dumps(pack).encode("utf-8")

            catalogue = CatalogueService(
                ctx.definitions, ctx.ecu_files, ctx.config.packs, fetcher=fake_fetch
            )
            fetched = catalogue.fetch_for_file(file.id)

            assert calls == [expected_url]  # queried by exact hash
            assert [s.name for s in fetched] == ["Pack en ligne"]
        finally:
            ctx.database.dispose()

    def test_url_404_returns_nothing(self, context: ApplicationContext, imported_file) -> None:
        context.config.packs.catalogue_urls = ["https://packs.example"]
        catalogue = CatalogueService(
            context.definitions, context.ecu_files, context.config.packs,
            fetcher=lambda url, timeout: None,  # always "not found"
        )
        assert catalogue.fetch_for_file(imported_file.id) == []


def test_packs_config_roundtrip(tmp_path) -> None:
    config_path = tmp_path / "calforge.toml"
    config = AppConfig(
        data_dir=tmp_path / "d", log_dir=tmp_path / "l", config_path=config_path
    )
    config.packs.catalogue_dirs = ["/mnt/nas/packs"]
    config.packs.catalogue_urls = ["https://packs.example"]
    config.packs.auto_fetch = True
    config.save()

    loaded = AppConfig.load(config_path)
    assert loaded.packs.catalogue_dirs == ["/mnt/nas/packs"]
    assert loaded.packs.catalogue_urls == ["https://packs.example"]
    assert loaded.packs.auto_fetch is True
