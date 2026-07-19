"""Map pack library panel: definition sources and their maps."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from calforge.app import ApplicationContext
from calforge.services.dto import DefinitionSourceDto, MapDefinitionDto
from calforge.ui.dialogs import show_error
from calforge.ui.models import _DtoTableModel

logger = logging.getLogger(__name__)


class _SourceTableModel(_DtoTableModel[DefinitionSourceDto]):
    HEADERS = ("Source de définitions", "Cartographies", "Importée le")

    def display(self, item: DefinitionSourceDto, column: int) -> str | None:
        if column == 0:
            return item.name
        if column == 1:
            return str(item.map_count)
        if column == 2:
            return item.created_at.strftime("%Y-%m-%d")
        return None

    def tooltip(self, item: DefinitionSourceDto) -> str | None:
        return item.description or None


class _DefinitionTableModel(_DtoTableModel[MapDefinitionDto]):
    HEADERS = ("Cartographie", "Catégorie", "Offset", "Dimensions", "Unité")

    def display(self, item: MapDefinitionDto, column: int) -> str | None:
        if column == 0:
            return item.name
        if column == 1:
            return item.category
        if column == 2:
            return f"0x{item.offset:X}"
        if column == 3:
            return item.shape_label
        if column == 4:
            return item.unit or "—"
        return None

    def tooltip(self, item: MapDefinitionDto) -> str | None:
        parts = [f"physique = brut × {item.factor} + {item.value_offset}"]
        if item.description:
            parts.append(item.description)
        return "\n".join(parts)


def _make_table(model) -> QTableView:
    table = QTableView()
    table.setModel(model)
    table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
    table.setAlternatingRowColors(True)
    table.horizontalHeader().setStretchLastSection(True)
    table.verticalHeader().setVisible(False)
    return table


class MapPackPanel(QWidget):
    def __init__(self, context: ApplicationContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context

        self._source_model = _SourceTableModel()
        self._source_table = _make_table(self._source_model)
        self._source_table.selectionModel().currentRowChanged.connect(self._on_source_selected)

        import_button = QPushButton("Importer un pack…")
        import_button.clicked.connect(self._import_pack)
        export_button = QPushButton("Exporter…")
        export_button.clicked.connect(self._export_pack)
        delete_button = QPushButton("Supprimer")
        delete_button.clicked.connect(self._delete_source)

        buttons = QHBoxLayout()
        for button in (import_button, export_button, delete_button):
            buttons.addWidget(button)
        buttons.addStretch()

        sources_panel = QWidget()
        sources_layout = QVBoxLayout(sources_panel)
        sources_layout.setContentsMargins(0, 0, 0, 0)
        sources_layout.addLayout(buttons)
        sources_layout.addWidget(self._source_table)

        self._definition_model = _DefinitionTableModel()
        self._definition_table = _make_table(self._definition_model)

        definitions_panel = QWidget()
        definitions_layout = QVBoxLayout(definitions_panel)
        definitions_layout.setContentsMargins(0, 0, 0, 0)
        definitions_layout.addWidget(QLabel("<b>Cartographies définies</b>"))
        definitions_layout.addWidget(self._definition_table)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(sources_panel)
        splitter.addWidget(definitions_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        hint = QLabel(
            "Format ouvert « calforge-pack/1 » (JSON). Un pack s'applique à un fichier "
            "par empreinte SHA-256, signature d'octets ou taille — depuis l'onglet "
            "d'analyse d'un fichier, bouton « Appliquer les définitions »."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8b939e;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(splitter)
        layout.addWidget(hint)
        self.refresh()

    def refresh(self) -> None:
        selected = self._selected_source()
        self._source_model.set_items(self._context.definitions.list_sources())
        if selected is not None:
            for row, source in enumerate(self._source_model.items()):
                if source.id == selected.id:
                    self._source_table.selectRow(row)
                    return
        self._definition_model.set_items([])

    def _selected_source(self) -> DefinitionSourceDto | None:
        index = self._source_table.currentIndex()
        return self._source_model.item_at(index.row()) if index.isValid() else None

    def _on_source_selected(self, current, _previous) -> None:
        source = self._source_model.item_at(current.row()) if current.isValid() else None
        self._definition_model.set_items(
            self._context.definitions.list_definitions(source.id) if source else []
        )

    def _import_pack(self) -> None:
        paths, _f = QFileDialog.getOpenFileNames(
            self, "Importer des packs", "", "Packs CalForge (*.calpack.json);;JSON (*.json)"
        )
        for path in paths:
            try:
                source = self._context.definitions.import_pack(Path(path))
            except Exception as exc:
                show_error(self, str(exc))
            else:
                logger.info("Pack imported from UI: %s", source.name)
        self.refresh()

    def _export_pack(self) -> None:
        source = self._selected_source()
        if source is None:
            return
        target, _f = QFileDialog.getSaveFileName(
            self, "Exporter le pack", f"{source.name}.calpack.json",
            "Packs CalForge (*.calpack.json)",
        )
        if not target:
            return
        try:
            self._context.definitions.export_pack(source.id, Path(target))
        except Exception as exc:
            show_error(self, f"Export échoué : {exc}")

    def _delete_source(self) -> None:
        source = self._selected_source()
        if source is None:
            return
        answer = QMessageBox.question(
            self,
            "Supprimer la source",
            f"Supprimer « {source.name} » et ses {source.map_count} définition(s) ?\n"
            "Les cartographies déjà validées sur vos fichiers sont conservées.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._context.definitions.delete_source(source.id)
            self.refresh()
