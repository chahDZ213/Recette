"""Global ECU file library with instant search across the whole workshop."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from calforge.app import ApplicationContext
from calforge.ui.models import EcuLibraryTableModel


class EcuLibraryPanel(QWidget):
    hex_requested = Signal(object)  # EcuFileDto

    def __init__(self, context: ApplicationContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context

        self._search = QLineEdit()
        self._search.setPlaceholderText(
            "Rechercher dans toute la bibliothèque (nom, SHA-256, format, véhicule…)"
        )
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(lambda _t: self.refresh())

        self._model = EcuLibraryTableModel()
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(False)
        self._table.doubleClicked.connect(self._on_double_click)

        self._count = QLabel()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self._search)
        layout.addWidget(self._table)
        layout.addWidget(self._count)
        self.refresh()

    def refresh(self) -> None:
        files = self._context.ecu_files.search(self._search.text())
        self._model.set_items(files)
        self._count.setText(f"{len(files)} fichier(s)")

    def _on_double_click(self, index) -> None:
        file = self._model.item_at(index.row())
        if file is not None:
            self.hex_requested.emit(file)
