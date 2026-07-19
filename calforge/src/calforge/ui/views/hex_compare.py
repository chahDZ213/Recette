"""Side-by-side hexadecimal comparison of two ECU files.

Both panes highlight the difference regions and scroll in lockstep; the
region list on the left jumps both views to the selected zone.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from calforge.analysis.diff import DiffResult, diff_bytes
from calforge.app import ApplicationContext
from calforge.services.dto import EcuFileDto
from calforge.ui.dialogs import show_error
from calforge.ui.models import HexTableModel, _DtoTableModel
from calforge.ui.theme import HIGHLIGHTS, PALETTE
from calforge.ui.workers import run_in_background

logger = logging.getLogger(__name__)


class _RegionTableModel(_DtoTableModel):
    HEADERS = ("Début", "Fin", "Octets modifiés")

    def display(self, item, column: int) -> str | None:
        if column == 0:
            return f"0x{item.offset:X}"
        if column == 1:
            return f"0x{item.end:X}"
        if column == 2:
            return str(item.changed_bytes)
        return None


def _make_hex_table(model: HexTableModel) -> QTableView:
    table = QTableView()
    table.setModel(model)
    table.horizontalHeader().setDefaultSectionSize(30)
    table.horizontalHeader().setStretchLastSection(True)
    table.verticalHeader().setDefaultSectionSize(22)
    return table


class HexCompareView(QWidget):
    def __init__(
        self,
        context: ApplicationContext,
        file_a: EcuFileDto,
        file_b: EcuFileDto,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._file_a = file_a
        self._file_b = file_b
        self._result: DiffResult | None = None
        self._sync_guard = False

        self._summary = QLabel("Comparaison en cours…")
        self._summary.setWordWrap(True)

        self._region_model = _RegionTableModel()
        self._region_table = QTableView()
        self._region_table.setModel(self._region_model)
        self._region_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._region_table.horizontalHeader().setStretchLastSection(True)
        self._region_table.verticalHeader().setVisible(False)
        self._region_table.selectionModel().currentRowChanged.connect(self._on_region_selected)

        prev_button = QPushButton("◀ Zone précédente")
        prev_button.clicked.connect(lambda: self._step_region(-1))
        next_button = QPushButton("Zone suivante ▶")
        next_button.clicked.connect(lambda: self._step_region(+1))
        nav = QHBoxLayout()
        nav.addWidget(prev_button)
        nav.addWidget(next_button)

        report_button = QPushButton("Rapport de comparaison (PDF/HTML)…")
        report_button.clicked.connect(self._export_report)

        regions_panel = QWidget()
        regions_layout = QVBoxLayout(regions_panel)
        regions_layout.setContentsMargins(0, 0, 0, 0)
        regions_layout.addWidget(QLabel("<b>Zones de différences</b>"))
        regions_layout.addWidget(self._region_table)
        regions_layout.addLayout(nav)
        regions_layout.addWidget(report_button)

        self._model_a = HexTableModel()
        self._model_b = HexTableModel()
        self._table_a = _make_hex_table(self._model_a)
        self._table_b = _make_hex_table(self._model_b)
        self._table_a.verticalScrollBar().valueChanged.connect(
            lambda value: self._sync_scroll(self._table_b, value)
        )
        self._table_b.verticalScrollBar().valueChanged.connect(
            lambda value: self._sync_scroll(self._table_a, value)
        )

        pane_a = self._labelled_pane(file_a.original_filename, self._table_a)
        pane_b = self._labelled_pane(file_b.original_filename, self._table_b)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(regions_panel)
        splitter.addWidget(pane_a)
        splitter.addWidget(pane_b)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 4)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self._summary)
        layout.addWidget(splitter)

        self._load()

    @staticmethod
    def _labelled_pane(title: str, table: QTableView) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(f"<b>{title}</b>")
        label.setStyleSheet(f"color: {PALETTE['accent']};")
        layout.addWidget(label)
        layout.addWidget(table)
        return pane

    def _load(self) -> None:
        service = self._context.ecu_files
        id_a, id_b = self._file_a.id, self._file_b.id

        def work() -> tuple[bytes, bytes, DiffResult]:
            data_a = service.read_content(id_a)
            data_b = service.read_content(id_b)
            return data_a, data_b, diff_bytes(data_a, data_b)

        def on_done(payload: object) -> None:
            data_a, data_b, result = payload  # type: ignore[misc]
            self._result = result
            self._model_a.set_data(data_a)
            self._model_b.set_data(data_b)
            highlights = [
                (region.offset, region.end, HIGHLIGHTS["diff"]())
                for region in result.regions
            ]
            self._model_a.set_highlights(highlights)
            self._model_b.set_highlights(highlights)
            self._region_model.set_items(list(result.regions))
            if result.identical:
                self._summary.setText("Les deux fichiers sont strictement identiques.")
            else:
                self._summary.setText(
                    f"{result.total_changed_bytes} octet(s) modifié(s) dans "
                    f"{len(result.regions)} zone(s)."
                )
                if result.regions:
                    self._region_table.selectRow(0)

        run_in_background(
            work,
            on_done=on_done,
            on_error=lambda message: show_error(self, f"Comparaison échouée : {message}"),
        )

    # ---------------------------------------------------------- navigation --

    def _sync_scroll(self, other: QTableView, value: int) -> None:
        if self._sync_guard:
            return
        self._sync_guard = True
        try:
            other.verticalScrollBar().setValue(value)
        finally:
            self._sync_guard = False

    def _on_region_selected(self, current, _previous) -> None:
        region = self._region_model.item_at(current.row()) if current.isValid() else None
        if region is None:
            return
        # Scroll both panes explicitly: relying on scrollbar mirroring alone
        # fails when a pane's scroll range is not yet computed (first layout).
        for model, table in ((self._model_a, self._table_a), (self._model_b, self._table_b)):
            last_offset = model.rowCount() * HexTableModel.BYTES_PER_ROW - 1
            if last_offset < 0:
                continue
            index = model.index_for_offset(min(region.offset, last_offset))
            table.scrollTo(index, QTableView.ScrollHint.PositionAtCenter)
            table.setCurrentIndex(index)

    def _step_region(self, delta: int) -> None:
        count = self._region_model.rowCount()
        if count == 0:
            return
        current = self._region_table.currentIndex().row()
        self._region_table.selectRow(max(0, min(count - 1, current + delta)))

    def _export_report(self) -> None:
        from calforge.ui.reporting import export_report

        id_a, id_b = self._file_a.id, self._file_b.id
        export_report(
            self,
            lambda: self._context.reports.comparison_report_html(id_a, id_b),
            "comparaison.pdf",
        )
