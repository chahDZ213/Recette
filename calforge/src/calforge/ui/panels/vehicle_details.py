"""Vehicle folder panel: identity sheet, projects, history, documents, ECU files.

Owns every vehicle-scoped interaction; the main window only routes selection,
drag & drop and domain events here, and executes the cross-panel requests
exposed as signals (hex view, comparison).
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from calforge.app import ApplicationContext
from calforge.data.models import EcuFileKind
from calforge.services.dto import EcuFileDto, VehicleDto
from calforge.ui.dialogs import (
    AttachmentMetaDialog,
    HistoryEntryDialog,
    ProjectDialog,
    show_error,
)
from calforge.ui.models import (
    AttachmentTableModel,
    EcuFileTableModel,
    HistoryTableModel,
    ProjectTableModel,
)
from calforge.ui.reporting import export_report
from calforge.ui.workers import run_in_background

logger = logging.getLogger(__name__)

# The import must accept ANY file — no format, ECU, make or year is ever
# rejected. "Tous les fichiers" is the default filter; the ECU list below is
# only a convenience shortcut, never a restriction (see ADR-0011). The known
# extensions span the common dump/read tools and formats across the industry.
_ECU_EXTENSIONS = (
    "*.bin *.ori *.mod *.ori1 *.ori2 *.mpc *.kp *.dtf *.hex *.ihex *.s19 *.s28 *.s37 "
    "*.frf *.sgo *.odx *.pdx *.simos *.dam *.damos *.a2l *.kess *.mpps *.ktag *.bdm "
    "*.jtag *.full *.read *.rd *.wr *.dam *.C16 *.M16 *.enc *.dec *.fls *.eep *.map "
    "*.dtc *.cal *.par *.tun *.ecu *.vr *.bmw *.dts *.checksum *.original"
)
IMPORT_FILTER = (
    "Tous les fichiers (*);;"
    f"Fichiers ECU connus ({_ECU_EXTENSIONS})"
)


def _make_table(model, *, stretch_last: bool = True) -> QTableView:
    table = QTableView()
    table.setModel(model)
    table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
    table.setAlternatingRowColors(True)
    table.horizontalHeader().setStretchLastSection(stretch_last)
    table.verticalHeader().setVisible(False)
    return table


class VehicleDetailsPanel(QWidget):
    hex_requested = Signal(object)  # EcuFileDto
    compare_requested = Signal(object, object)  # EcuFileDto, EcuFileDto
    status_message = Signal(str, int)

    def __init__(self, context: ApplicationContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self._vehicle: VehicleDto | None = None

        self._tabs = QTabWidget()
        self._build_sheet_tab()
        self._build_projects_tab()
        self._build_history_tab()
        self._build_documents_tab()
        self._build_files_tab()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self._tabs)
        self.set_vehicle(None)

    # ------------------------------------------------------------- tabs ----

    def _build_sheet_tab(self) -> None:
        self._sheet = QLabel()
        self._sheet.setWordWrap(True)
        self._sheet.setTextFormat(Qt.TextFormat.RichText)
        self._sheet.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._sheet.setContentsMargins(8, 8, 8, 8)

        report_button = QPushButton("Rapport de dossier (PDF/HTML)…")
        report_button.clicked.connect(self._export_vehicle_report)
        json_button = QPushButton("Exporter (JSON)…")
        json_button.clicked.connect(self._export_vehicle_json)
        csv_button = QPushButton("Fichiers (CSV)…")
        csv_button.clicked.connect(self._export_files_csv)

        export_row = QHBoxLayout()
        for button in (report_button, json_button, csv_button):
            export_row.addWidget(button)
        export_row.addStretch()

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self._sheet, stretch=1)
        layout.addLayout(export_row)
        self._tabs.addTab(container, "Fiche")

    def _build_projects_tab(self) -> None:
        self._project_model = ProjectTableModel()
        self._project_table = _make_table(self._project_model)
        self._project_table.doubleClicked.connect(lambda _i: self._edit_project())

        add_button = QPushButton("Nouveau projet…")
        add_button.clicked.connect(self._new_project)
        edit_button = QPushButton("Modifier…")
        edit_button.clicked.connect(self._edit_project)

        self._tabs.addTab(
            self._tab_layout([add_button, edit_button], self._project_table), "Projets"
        )

    def _build_history_tab(self) -> None:
        self._history_model = HistoryTableModel()
        self._history_table = _make_table(self._history_model)

        add_button = QPushButton("Ajouter une entrée…")
        add_button.clicked.connect(self._new_history_entry)
        delete_button = QPushButton("Supprimer")
        delete_button.clicked.connect(self._delete_history_entry)

        self._tabs.addTab(
            self._tab_layout([add_button, delete_button], self._history_table), "Historique"
        )

    def _build_documents_tab(self) -> None:
        self._attachment_model = AttachmentTableModel()
        self._attachment_table = _make_table(self._attachment_model)

        add_button = QPushButton("Ajouter…")
        add_button.clicked.connect(self._add_attachments)
        export_button = QPushButton("Exporter…")
        export_button.clicked.connect(self._export_attachment)
        remove_button = QPushButton("Retirer")
        remove_button.clicked.connect(self._remove_attachment)

        self._tabs.addTab(
            self._tab_layout([add_button, export_button, remove_button], self._attachment_table),
            "Documents",
        )

    def _build_files_tab(self) -> None:
        self._file_model = EcuFileTableModel()
        self._file_table = _make_table(self._file_model)
        self._file_table.doubleClicked.connect(lambda _i: self._request_hex())
        self._file_table.selectionModel().selectionChanged.connect(self._update_file_buttons)

        self._import_button = QPushButton("Importer…")
        self._import_button.clicked.connect(self.open_import_dialog)
        self._version_button = QPushButton("Importer une version…")
        self._version_button.setToolTip(
            "Importer un fichier modifié dérivé du fichier sélectionné"
        )
        self._version_button.clicked.connect(self._import_version_dialog)
        self._compare_button = QPushButton("Comparer")
        self._compare_button.clicked.connect(self._request_compare)
        self._hex_button = QPushButton("Ouvrir / Éditer")
        self._hex_button.setToolTip("Vue hexadécimale, détection et édition de cartographies")
        self._hex_button.clicked.connect(self._request_hex)
        self._export_button = QPushButton("Exporter…")
        self._export_button.setToolTip("Enregistrer ce fichier (ex. modifié) sur le disque")
        self._export_button.clicked.connect(self._export_file)

        self._tabs.addTab(
            self._tab_layout(
                [
                    self._import_button,
                    self._version_button,
                    self._compare_button,
                    self._hex_button,
                    self._export_button,
                ],
                self._file_table,
            ),
            "Fichiers ECU",
        )
        self._update_file_buttons()

    @staticmethod
    def _tab_layout(buttons: list[QPushButton], table: QTableView) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        row = QHBoxLayout()
        for button in buttons:
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(table)
        return container

    # --------------------------------------------------------- selection ---

    @property
    def current_vehicle(self) -> VehicleDto | None:
        return self._vehicle

    def set_vehicle(self, vehicle: VehicleDto | None) -> None:
        self._vehicle = vehicle
        enabled = vehicle is not None
        self._tabs.setEnabled(enabled)
        if vehicle is None:
            self._sheet.setText("<i>Sélectionnez un véhicule.</i>")
            self._project_model.set_items([])
            self._history_model.set_items([])
            self._attachment_model.set_items([])
            self._file_model.set_files([])
            self._update_file_buttons()
            return
        self._render_sheet(vehicle)
        self.refresh_projects()
        self.refresh_history()
        self.refresh_documents()
        self.refresh_files()

    def _render_sheet(self, vehicle: VehicleDto) -> None:
        rows = [f"<h3>{vehicle.display_name}</h3>"]
        for label, value in (
            ("VIN", vehicle.vin),
            ("Immatriculation", vehicle.license_plate),
            ("Code moteur", vehicle.engine_code),
            ("ECU", vehicle.ecu_type),
        ):
            if value:
                rows.append(f"<b>{label} :</b> {value}<br>")
        if vehicle.notes:
            rows.append(f"<p>{vehicle.notes}</p>")
        self._sheet.setText("".join(rows))

    # ----------------------------------------------------------- reports ---

    def _slug(self) -> str:
        vehicle = self._vehicle
        return (
            "".join(c if c.isalnum() else "_" for c in vehicle.display_name)
            if vehicle
            else "vehicule"
        )

    def _export_vehicle_report(self) -> None:
        if self._vehicle is None:
            return
        vehicle_id = self._vehicle.id
        export_report(
            self,
            lambda: self._context.reports.vehicle_report_html(vehicle_id),
            f"dossier_{self._slug()}.pdf",
            on_status=lambda message, timeout: self.status_message.emit(message, timeout),
        )

    def _export_vehicle_json(self) -> None:
        if self._vehicle is None:
            return
        target, _f = QFileDialog.getSaveFileName(
            self, "Exporter en JSON", f"dossier_{self._slug()}.json", "JSON (*.json)"
        )
        if not target:
            return
        try:
            self._context.reports.export_vehicle_json(self._vehicle.id, Path(target))
            self.status_message.emit(f"Exporté : {target}", 6000)
        except Exception as exc:
            show_error(self, f"Export JSON échoué : {exc}")

    def _export_files_csv(self) -> None:
        if self._vehicle is None:
            return
        target, _f = QFileDialog.getSaveFileName(
            self, "Exporter les fichiers (CSV)", f"fichiers_{self._slug()}.csv", "CSV (*.csv)"
        )
        if not target:
            return
        try:
            self._context.reports.export_files_csv(self._vehicle.id, Path(target))
            self.status_message.emit(f"Exporté : {target}", 6000)
        except Exception as exc:
            show_error(self, f"Export CSV échoué : {exc}")

    # ---------------------------------------------------------- refresh ----

    def refresh_projects(self) -> None:
        if self._vehicle is not None:
            self._project_model.set_items(
                self._context.projects.list_for_vehicle(self._vehicle.id)
            )

    def refresh_history(self) -> None:
        if self._vehicle is not None:
            self._history_model.set_items(
                self._context.history.list_for_vehicle(self._vehicle.id)
            )

    def refresh_documents(self) -> None:
        if self._vehicle is not None:
            self._attachment_model.set_items(
                self._context.attachments.list_for_vehicle(self._vehicle.id)
            )

    def refresh_files(self) -> None:
        if self._vehicle is not None:
            self._file_model.set_files(
                self._context.ecu_files.list_for_vehicle(self._vehicle.id)
            )
        self._update_file_buttons()

    # ---------------------------------------------------------- projects ---

    def _new_project(self) -> None:
        if self._vehicle is None:
            return
        dialog = ProjectDialog(self._vehicle.id, self)
        if dialog.exec() and (data := dialog.project_input()):
            try:
                self._context.projects.create(data)
            except Exception as exc:
                show_error(self, f"Création du projet impossible : {exc}")

    def _edit_project(self) -> None:
        if self._vehicle is None:
            return
        index = self._project_table.currentIndex()
        project = self._project_model.item_at(index.row()) if index.isValid() else None
        if project is None:
            return
        dialog = ProjectDialog(self._vehicle.id, self, project=project)
        if dialog.exec() and (data := dialog.project_input()):
            try:
                self._context.projects.update(project.id, data)
            except Exception as exc:
                show_error(self, f"Mise à jour du projet impossible : {exc}")

    # ----------------------------------------------------------- history ---

    def _new_history_entry(self) -> None:
        if self._vehicle is None:
            return
        dialog = HistoryEntryDialog(self._vehicle.id, self)
        if dialog.exec() and (data := dialog.entry_input()):
            try:
                self._context.history.add(data)
            except Exception as exc:
                show_error(self, f"Ajout impossible : {exc}")

    def _delete_history_entry(self) -> None:
        index = self._history_table.currentIndex()
        entry = self._history_model.item_at(index.row()) if index.isValid() else None
        if entry is None:
            return
        answer = QMessageBox.question(
            self, "Supprimer", f"Supprimer l'entrée « {entry.title} » ?"
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._context.history.delete(entry.id)

    # --------------------------------------------------------- documents ---

    def _add_attachments(self) -> None:
        if self._vehicle is None:
            return
        paths, _f = QFileDialog.getOpenFileNames(self, "Ajouter des documents")
        if not paths:
            return
        dialog = AttachmentMetaDialog([Path(p).name for p in paths], self)
        if not dialog.exec():
            return
        category, notes = dialog.category(), dialog.notes()
        vehicle_id = self._vehicle.id
        service = self._context.attachments
        for path in paths:
            run_in_background(
                lambda p=Path(path): service.add(vehicle_id, p, category=category, notes=notes),
                on_done=lambda _dto: None,  # AttachmentAdded refreshes the UI
                on_error=lambda message: show_error(self, f"Ajout échoué : {message}"),
            )

    def _export_attachment(self) -> None:
        index = self._attachment_table.currentIndex()
        attachment = self._attachment_model.item_at(index.row()) if index.isValid() else None
        if attachment is None:
            return
        target, _f = QFileDialog.getSaveFileName(
            self, "Exporter le document", attachment.original_filename
        )
        if not target:
            return
        try:
            self._context.attachments.export_to(attachment.id, Path(target))
            self.status_message.emit(f"Exporté : {target}", 5000)
        except Exception as exc:
            show_error(self, f"Export échoué : {exc}")

    def _remove_attachment(self) -> None:
        index = self._attachment_table.currentIndex()
        attachment = self._attachment_model.item_at(index.row()) if index.isValid() else None
        if attachment is None:
            return
        answer = QMessageBox.question(
            self,
            "Retirer le document",
            f"Retirer « {attachment.original_filename} » de ce véhicule ?\n"
            "Le contenu reste conservé dans le stockage interne.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._context.attachments.delete(attachment.id)

    # ------------------------------------------------------------- files ---

    def selected_files(self) -> list[EcuFileDto]:
        rows = {index.row() for index in self._file_table.selectionModel().selectedRows()}
        files = [self._file_model.file_at(row) for row in sorted(rows)]
        return [f for f in files if f is not None]

    def _update_file_buttons(self, *_args) -> None:
        has_vehicle = self._vehicle is not None
        selected = self.selected_files() if has_vehicle else []
        self._import_button.setEnabled(has_vehicle)
        self._version_button.setEnabled(len(selected) == 1)
        self._compare_button.setEnabled(len(selected) == 2)
        self._hex_button.setEnabled(len(selected) == 1)
        self._export_button.setEnabled(len(selected) == 1)

    def open_import_dialog(self) -> None:
        if self._vehicle is None:
            return
        paths, _f = QFileDialog.getOpenFileNames(
            self, "Importer des fichiers ECU (tout format accepté)", "", IMPORT_FILTER
        )
        self.import_paths([Path(p) for p in paths])

    def _import_version_dialog(self) -> None:
        selected = self.selected_files()
        if len(selected) != 1:
            return
        parent_file = selected[0]
        paths, _f = QFileDialog.getOpenFileNames(
            self,
            f"Importer une version dérivée de {parent_file.original_filename}",
            "",
            IMPORT_FILTER,
        )
        self.import_paths([Path(p) for p in paths], parent_file_id=parent_file.id)

    def import_paths(self, paths: list[Path], *, parent_file_id: int | None = None) -> None:
        """Import files for the current vehicle (used by dialogs and drag & drop)."""
        if self._vehicle is None or not paths:
            return
        vehicle_id = self._vehicle.id
        service = self._context.ecu_files
        for path in paths:
            self.status_message.emit(f"Import de {path.name}…", 0)
            run_in_background(
                lambda p=path: service.import_file(
                    p,
                    vehicle_id=vehicle_id,
                    parent_file_id=parent_file_id,
                    kind=EcuFileKind.UNKNOWN,
                ),
                on_done=lambda _dto: None,  # EcuFileImported refreshes the UI
                on_error=lambda message: show_error(self, f"Import échoué : {message}"),
            )

    def _request_hex(self) -> None:
        selected = self.selected_files()
        if len(selected) == 1:
            self.hex_requested.emit(selected[0])

    def _request_compare(self) -> None:
        selected = self.selected_files()
        if len(selected) == 2:
            self.compare_requested.emit(selected[0], selected[1])

    def _export_file(self) -> None:
        selected = self.selected_files()
        if len(selected) != 1:
            return
        file = selected[0]
        target, _f = QFileDialog.getSaveFileName(
            self, "Exporter le fichier ECU", file.original_filename, IMPORT_FILTER
        )
        if not target:
            return
        service = self._context.ecu_files
        run_in_background(
            lambda: service.export_to(file.id, Path(target)),
            on_done=lambda saved: self.status_message.emit(f"Exporté : {saved}", 6000),
            on_error=lambda message: show_error(self, f"Export échoué : {message}"),
        )
