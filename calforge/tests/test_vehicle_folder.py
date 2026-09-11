"""Tests for v0.2: attachments, history timeline, ECU library and versioning."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from calforge.app import ApplicationContext
from calforge.data.models import AttachmentCategory, EcuFileKind, HistoryEntryType
from calforge.services.attachments import AttachmentNotFoundError
from calforge.services.dto import HistoryEntryInput, VehicleInput
from calforge.services.events import AttachmentAdded, HistoryEntryAdded


def make_vehicle(context: ApplicationContext, **overrides):
    data = {"make": "Volkswagen", "model": "Golf GTI", "year": 2019} | overrides
    return context.vehicles.create(VehicleInput(**data))


def test_migration_0002_schema(context: ApplicationContext, app_config) -> None:
    with sqlite3.connect(app_config.database_path) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"attachments", "history_entries"} <= tables
        columns = {row[1] for row in conn.execute("PRAGMA table_info(ecu_files)")}
        assert "parent_file_id" in columns


class TestAttachments:
    def test_add_list_read_roundtrip(
        self, context: ApplicationContext, tmp_path: Path
    ) -> None:
        vehicle = make_vehicle(context)
        invoice = tmp_path / "facture-2026-001.pdf"
        invoice.write_bytes(b"%PDF-1.7 fake invoice")
        events = []
        context.bus.subscribe(AttachmentAdded, events.append)

        dto = context.attachments.add(
            vehicle.id, invoice, category=AttachmentCategory.INVOICE, notes="Stage 1"
        )

        assert dto.category == AttachmentCategory.INVOICE
        assert len(events) == 1
        listed = context.attachments.list_for_vehicle(vehicle.id)
        assert [a.id for a in listed] == [dto.id]
        assert context.attachments.read_content(dto.id) == invoice.read_bytes()

    def test_export(self, context: ApplicationContext, tmp_path: Path) -> None:
        vehicle = make_vehicle(context)
        photo = tmp_path / "moteur.jpg"
        photo.write_bytes(b"\xff\xd8\xff jpeg-data")
        dto = context.attachments.add(vehicle.id, photo, category=AttachmentCategory.PHOTO)

        target = context.attachments.export_to(dto.id, tmp_path / "out" / "moteur.jpg")
        assert target.read_bytes() == photo.read_bytes()

    def test_delete_keeps_blob(self, context: ApplicationContext, tmp_path: Path) -> None:
        vehicle = make_vehicle(context)
        doc = tmp_path / "rapport.txt"
        doc.write_bytes(b"rapport")
        dto = context.attachments.add(vehicle.id, doc)

        context.attachments.delete(dto.id)

        assert context.attachments.list_for_vehicle(vehicle.id) == []
        with pytest.raises(AttachmentNotFoundError):
            context.attachments.get(dto.id)
        # The content itself is never destroyed.
        assert context.blobs.read_bytes(dto.sha256) == b"rapport"


class TestHistory:
    def test_add_and_chronological_order(self, context: ApplicationContext) -> None:
        vehicle = make_vehicle(context)
        base = datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
        events = []
        context.bus.subscribe(HistoryEntryAdded, events.append)

        for offset, (entry_type, title) in enumerate(
            [
                (HistoryEntryType.INTERVENTION, "Remplacement turbo"),
                (HistoryEntryType.DIAGNOSTIC, "Lecture des codes défaut"),
                (HistoryEntryType.ROAD_TEST, "Essai après Stage 1"),
            ]
        ):
            context.history.add(
                HistoryEntryInput(
                    vehicle_id=vehicle.id,
                    entry_type=entry_type,
                    title=title,
                    occurred_at=base + timedelta(days=offset),
                )
            )

        timeline = context.history.list_for_vehicle(vehicle.id)
        assert [e.title for e in timeline] == [
            "Essai après Stage 1",
            "Lecture des codes défaut",
            "Remplacement turbo",
        ]  # newest first
        assert len(events) == 3

    def test_delete(self, context: ApplicationContext) -> None:
        vehicle = make_vehicle(context)
        entry = context.history.add(
            HistoryEntryInput(
                vehicle_id=vehicle.id,
                title="Note",
                occurred_at=datetime.now(UTC),
            )
        )
        context.history.delete(entry.id)
        assert context.history.list_for_vehicle(vehicle.id) == []

    def test_blank_title_rejected(self) -> None:
        with pytest.raises(ValueError):
            HistoryEntryInput(vehicle_id=1, title="   ", occurred_at=datetime.now(UTC))


class TestLibraryAndVersioning:
    def test_import_version_links_parent_and_kind(
        self, context: ApplicationContext, sample_bin: Path, tmp_path: Path
    ) -> None:
        vehicle = make_vehicle(context)
        original = context.ecu_files.import_file(
            sample_bin, vehicle_id=vehicle.id, kind=EcuFileKind.ORIGINAL
        )

        modified_path = tmp_path / "stage1.bin"
        payload = bytearray(sample_bin.read_bytes())
        payload[0x40] ^= 0x55
        modified_path.write_bytes(payload)

        version = context.ecu_files.import_file(
            modified_path, vehicle_id=vehicle.id, parent_file_id=original.id
        )

        assert version.parent_file_id == original.id
        assert version.kind == EcuFileKind.MODIFIED  # inferred from lineage
        assert version.parent_label == sample_bin.name
        derivatives = context.ecu_files.list_derivatives(original.id)
        assert [d.id for d in derivatives] == [version.id]

    def test_import_version_with_unknown_parent_fails(
        self, context: ApplicationContext, sample_bin: Path
    ) -> None:
        from calforge.services.ecufiles import EcuFileNotFoundError

        with pytest.raises(EcuFileNotFoundError):
            context.ecu_files.import_file(sample_bin, parent_file_id=999)

    def test_search_across_fields(
        self, context: ApplicationContext, sample_bin: Path, tmp_path: Path
    ) -> None:
        golf = make_vehicle(context, make="Volkswagen", model="Golf GTI")
        bmw = make_vehicle(context, make="BMW", model="M340i")

        context.ecu_files.import_file(sample_bin, vehicle_id=golf.id)
        other = tmp_path / "m340i_original.bin"
        other.write_bytes(b"bmw-dump-content")
        imported = context.ecu_files.import_file(other, vehicle_id=bmw.id)

        by_vehicle = context.ecu_files.search("M340")
        assert [f.id for f in by_vehicle] == [imported.id]
        assert by_vehicle[0].vehicle_label == "BMW M340i"

        by_filename = context.ecu_files.search("m340i_orig")
        assert [f.id for f in by_filename] == [imported.id]

        by_hash = context.ecu_files.search(imported.sha256[:16])
        assert [f.id for f in by_hash] == [imported.id]

        assert len(context.ecu_files.search("")) == 2
