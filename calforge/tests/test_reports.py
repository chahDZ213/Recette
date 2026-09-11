"""Tests for v0.6: HTML reports, CSV/JSON exports, and Qt PDF rendering."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from tests.test_mapdetect import build_synthetic_dump

from calforge.app import ApplicationContext
from calforge.data.models import HistoryEntryType, MapCandidateStatus
from calforge.services.dto import HistoryEntryInput, ProjectInput, VehicleInput


@pytest.fixture
def populated_vehicle(context: ApplicationContext, tmp_path: Path):
    vehicle = context.vehicles.create(
        VehicleInput(make="Volkswagen", model="Golf GTI", year=2019, engine_code="DKFA")
    )
    context.projects.create(ProjectInput(vehicle_id=vehicle.id, name="Stage 1"))
    context.history.add(
        HistoryEntryInput(
            vehicle_id=vehicle.id,
            entry_type=HistoryEntryType.CALIBRATION,
            title="Flash Stage 1",
            content="Base sauvegardée avant écriture.",
            occurred_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
        )
    )
    data, offset = build_synthetic_dump()
    path = tmp_path / "golf.bin"
    path.write_bytes(data)
    file = context.ecu_files.import_file(path, vehicle_id=vehicle.id)
    candidates = context.analysis.detect_maps(file.id)
    target = next(c for c in candidates if c.offset == offset)
    context.analysis.set_candidate_status(
        target.id, MapCandidateStatus.VALIDATED, name="Injection charge/régime"
    )
    return vehicle, file


class TestVehicleReport:
    def test_html_contains_key_data(self, context: ApplicationContext, populated_vehicle) -> None:
        vehicle, _file = populated_vehicle
        html = context.reports.vehicle_report_html(vehicle.id)

        assert "Volkswagen Golf GTI 2019" in html
        assert "Stage 1" in html
        assert "Flash Stage 1" in html
        assert "golf.bin" in html
        assert "Injection charge/régime" in html  # validated map listed
        assert "généré automatiquement" in html  # honesty disclaimer

    def test_save_html(self, context: ApplicationContext, populated_vehicle, tmp_path) -> None:
        vehicle, _file = populated_vehicle
        html = context.reports.vehicle_report_html(vehicle.id)
        out = context.reports.save_html(html, tmp_path / "report.html")
        assert out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


class TestComparisonReport:
    def test_report_lists_regions_and_overlap(
        self, context: ApplicationContext, populated_vehicle, tmp_path
    ) -> None:
        vehicle, file = populated_vehicle
        data = bytearray(context.ecu_files.read_content(file.id))
        # Change a byte inside the validated map region.
        candidate = next(
            c
            for c in context.analysis.list_candidates(file.id)
            if c.status == MapCandidateStatus.VALIDATED
        )
        data[candidate.offset + 2] ^= 0xFF
        mod = tmp_path / "mod.bin"
        mod.write_bytes(bytes(data))
        other = context.ecu_files.import_file(mod, vehicle_id=vehicle.id)

        html = context.reports.comparison_report_html(file.id, other.id)
        assert "octet(s) modifié(s)" in html
        assert "Injection charge/régime" in html  # overlap flagged


class TestExports:
    def test_json_export_roundtrips(
        self, context: ApplicationContext, populated_vehicle, tmp_path
    ) -> None:
        vehicle, _file = populated_vehicle
        out = context.reports.export_vehicle_json(vehicle.id, tmp_path / "v.json")
        payload = json.loads(out.read_text(encoding="utf-8"))

        assert payload["vehicle"]["make"] == "Volkswagen"
        assert payload["projects"][0]["name"] == "Stage 1"
        assert payload["files"][0]["validated_maps"][0]["name"] == "Injection charge/régime"

    def test_csv_export_has_header_and_rows(
        self, context: ApplicationContext, populated_vehicle, tmp_path
    ) -> None:
        vehicle, _file = populated_vehicle
        out = context.reports.export_files_csv(vehicle.id, tmp_path / "files.csv")
        lines = out.read_text(encoding="utf-8").splitlines()
        assert lines[0].startswith("filename,vehicle,kind")
        assert "golf.bin" in lines[1]


class TestPdfRendering:
    def test_html_to_pdf_produces_pdf(self, context: ApplicationContext, populated_vehicle, tmp_path) -> None:
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QApplication

        from calforge.reporting.pdf import html_to_pdf

        QApplication.instance() or QApplication([])
        vehicle, _file = populated_vehicle
        html = context.reports.vehicle_report_html(vehicle.id)

        out = html_to_pdf(html, tmp_path / "report.pdf")
        blob = out.read_bytes()
        assert blob.startswith(b"%PDF")  # valid PDF magic
        assert len(blob) > 1000  # non-trivial content
