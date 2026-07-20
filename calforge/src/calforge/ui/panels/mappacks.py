"""Map pack library panel: definition sources and their maps."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
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
        layout.addWidget(splitter, 1)
        layout.addWidget(hint)
        layout.addWidget(self._build_catalogue_box())
        self.refresh()

    # -------------------------------------------------- automatic catalogue --

    def _build_catalogue_box(self) -> QGroupBox:
        """Configuration for the automatic pack catalogue (ADR-0013).

        Lets the user register sources they are entitled to use (local folders
        / NAS / synced drives, or base URLs they own or subscribe to) and opt
        into fetching a matching pack on its own when a file is imported.
        """
        box = QGroupBox("Catalogue automatique")
        box_layout = QVBoxLayout(box)

        self._auto_fetch_check = QCheckBox(
            "Chercher automatiquement un pack à l'import d'un fichier"
        )
        self._auto_fetch_check.setChecked(self._context.config.packs.auto_fetch)
        self._auto_fetch_check.toggled.connect(self._on_auto_fetch_toggled)
        box_layout.addWidget(self._auto_fetch_check)

        self._sources_list = QListWidget()
        self._sources_list.setToolTip(
            "Sources que vous configurez et êtes en droit d'utiliser : dossiers "
            "locaux / NAS / disques synchronisés, ou URLs de base que vous "
            "possédez ou auxquelles vous êtes abonné."
        )
        self._sources_list.setMaximumHeight(110)
        box_layout.addWidget(self._sources_list)

        source_buttons = QHBoxLayout()
        add_dir = QPushButton("Ajouter un dossier…")
        add_dir.clicked.connect(self._add_catalogue_dir)
        add_url = QPushButton("Ajouter une URL…")
        add_url.clicked.connect(self._add_catalogue_url)
        remove_source = QPushButton("Retirer")
        remove_source.clicked.connect(self._remove_catalogue_source)
        for button in (add_dir, add_url, remove_source):
            source_buttons.addWidget(button)
        source_buttons.addStretch()
        box_layout.addLayout(source_buttons)

        catalogue_hint = QLabel(
            "CalForge ne télécharge un pack que depuis vos propres sources — "
            "jamais en fouillant le web. Une URL de base est interrogée pour "
            "l'empreinte exacte du fichier (« &lt;url&gt;/&lt;sha256&gt;.calpack.json »). "
            "Sans source configurée, aucune connexion réseau n'est effectuée."
        )
        catalogue_hint.setWordWrap(True)
        catalogue_hint.setStyleSheet("color: #8b939e;")
        box_layout.addWidget(catalogue_hint)

        self._refresh_catalogue_sources()
        return box

    def _refresh_catalogue_sources(self) -> None:
        self._sources_list.clear()
        packs = self._context.config.packs
        for directory in packs.catalogue_dirs:
            item = QListWidgetItem(f"📁  {directory}")
            item.setData(Qt.ItemDataRole.UserRole, ("dir", directory))
            self._sources_list.addItem(item)
        for url in packs.catalogue_urls:
            item = QListWidgetItem(f"🌐  {url}")
            item.setData(Qt.ItemDataRole.UserRole, ("url", url))
            self._sources_list.addItem(item)

    def _on_auto_fetch_toggled(self, checked: bool) -> None:
        self._context.config.packs.auto_fetch = checked
        self._context.config.save()

    def _add_catalogue_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choisir un dossier de packs")
        if not directory:
            return
        packs = self._context.config.packs
        if directory not in packs.catalogue_dirs:
            packs.catalogue_dirs.append(directory)
            self._context.config.save()
            self._refresh_catalogue_sources()

    def _add_catalogue_url(self) -> None:
        url, ok = QInputDialog.getText(
            self,
            "Ajouter une URL de catalogue",
            "URL de base (l'app demandera « <url>/<sha256>.calpack.json ») :",
        )
        url = url.strip()
        if not ok or not url:
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            show_error(self, "L'URL doit commencer par http:// ou https://.")
            return
        packs = self._context.config.packs
        if url not in packs.catalogue_urls:
            packs.catalogue_urls.append(url)
            self._context.config.save()
            self._refresh_catalogue_sources()

    def _remove_catalogue_source(self) -> None:
        item = self._sources_list.currentItem()
        if item is None:
            return
        kind, value = item.data(Qt.ItemDataRole.UserRole)
        packs = self._context.config.packs
        if kind == "dir" and value in packs.catalogue_dirs:
            packs.catalogue_dirs.remove(value)
        elif kind == "url" and value in packs.catalogue_urls:
            packs.catalogue_urls.remove(value)
        self._context.config.save()
        self._refresh_catalogue_sources()

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
