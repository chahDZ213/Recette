"""Report service — gathers data across services and produces documents.

Everything here is Qt-free and returns strings/paths, so it is fully testable
headless. PDF rendering (Qt-bound) is applied by the UI via
``reporting.pdf.html_to_pdf`` on the returned HTML.
"""

from __future__ import annotations

import logging
from pathlib import Path

from calforge.data.models import MapCandidateStatus
from calforge.reporting import documents, exports
from calforge.reporting.documents import VehicleReportData
from calforge.services.analysis import AnalysisService
from calforge.services.ecufiles import EcuFileService
from calforge.services.history import HistoryService
from calforge.services.projects import ProjectService
from calforge.services.vehicles import VehicleService

logger = logging.getLogger(__name__)


class ReportService:
    def __init__(
        self,
        vehicles: VehicleService,
        projects: ProjectService,
        history: HistoryService,
        ecu_files: EcuFileService,
        analysis: AnalysisService,
    ) -> None:
        self._vehicles = vehicles
        self._projects = projects
        self._history = history
        self._files = ecu_files
        self._analysis = analysis

    def _vehicle_data(self, vehicle_id: int) -> VehicleReportData:
        vehicle = self._vehicles.get(vehicle_id)
        files = self._files.list_for_vehicle(vehicle_id)
        validated: dict[int, list] = {}
        for file in files:
            maps = [
                c
                for c in self._analysis.list_candidates(file.id)
                if c.status == MapCandidateStatus.VALIDATED
            ]
            if maps:
                validated[file.id] = maps
        return VehicleReportData(
            vehicle=vehicle,
            projects=self._projects.list_for_vehicle(vehicle_id),
            history=self._history.list_for_vehicle(vehicle_id),
            files=files,
            validated_maps=validated,
        )

    # -------------------------------------------------------------- HTML --

    def vehicle_report_html(self, vehicle_id: int) -> str:
        return documents.render_vehicle_report(self._vehicle_data(vehicle_id))

    def comparison_report_html(self, file_id_a: int, file_id_b: int) -> str:
        file_a = self._files.get(file_id_a)
        file_b = self._files.get(file_id_b)
        result = self._files.compare(file_id_a, file_id_b)
        candidates = self._analysis.list_candidates(file_id_a)
        return documents.render_comparison_report(file_a, file_b, result, candidates)

    # ------------------------------------------------------------- files --

    def save_html(self, html: str, target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        return target

    def export_vehicle_json(self, vehicle_id: int, target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(exports.vehicle_to_json(self._vehicle_data(vehicle_id)), encoding="utf-8")
        logger.info("Exported vehicle #%d as JSON to %s", vehicle_id, target)
        return target

    def export_files_csv(self, vehicle_id: int | None, target: Path) -> Path:
        files = (
            self._files.list_for_vehicle(vehicle_id)
            if vehicle_id is not None
            else self._files.list_all()
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(exports.files_to_csv(files), encoding="utf-8")
        logger.info("Exported %d file record(s) as CSV to %s", len(files), target)
        return target
