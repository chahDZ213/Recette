"""Main application window: dockable panels around a tabbed document area."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtGui import QAction, QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from calforge import APP_NAME, __version__
from calforge.app import ApplicationContext
from calforge.data.models import EcuFileKind
from calforge.services.dto import EcuFileDto, VehicleDto
from calforge.services.events import (
    EcuFileImported,
    VehicleCreated,
    VehicleDeleted,
    VehicleUpdated,
)
from calforge.ui.dialogs import DiffResultDialog, VehicleDialog, show_error
from calforge.ui.dispatch import EventBridge, QtLogHandler
from calforge.ui.models import EcuFileTableModel, HexTableModel, VehicleListModel
from calforge.ui.workers import run_in_background

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, context: ApplicationContext) -> None:
        super().__init__()
        self._context = context
        self._current_vehicle: VehicleDto | None = None
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1400, 860)
        self.setAcceptDrops(True)
        self.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks | QMainWindow.DockOption.AllowNestedDocks
        )

        self._build_central_area()
        self._build_vehicle_dock()
        self._build_details_dock()
        self._build_log_dock()
        self._build_actions()
        self._connect_events()
        self._restore_layout()
        self.refresh_vehicles()
        self.statusBar().showMessage("Prêt")

    # ------------------------------------------------------------------ UI --

    def _build_central_area(self) -> None:
        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)

        welcome = QLabel(
            f"<h2>{APP_NAME}</h2>"
            "<p>Assistant professionnel de calibration ECU.</p>"
            "<p>Créez un véhicule (Ctrl+N), puis importez ses fichiers ECU "
            "(Ctrl+I ou glisser-déposer).</p>"
        )
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tabs.addTab(welcome, "Bienvenue")
        self._tabs.tabBar().setTabButton(0, self._tabs.tabBar().ButtonPosition.RightSide, None)
        self.setCentralWidget(self._tabs)

    def _build_vehicle_dock(self) -> None:
        self._vehicle_model = VehicleListModel()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Rechercher (marque, VIN, ECU…)")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search)

        self._vehicle_list = QListView()
        self._vehicle_list.setModel(self._vehicle_model)
        self._vehicle_list.setAlternatingRowColors(True)
        self._vehicle_list.selectionModel().currentChanged.connect(self._on_vehicle_selected)
        self._vehicle_list.doubleClicked.connect(lambda _i: self._edit_vehicle())

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self._search)
        layout.addWidget(self._vehicle_list)

        dock = QDockWidget("Véhicules", self)
        dock.setObjectName("dock_vehicles")
        dock.setWidget(container)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    def _build_details_dock(self) -> None:
        self._details_label = QLabel("Sélectionnez un véhicule.")
        self._details_label.setWordWrap(True)
        self._details_label.setTextFormat(Qt.TextFormat.RichText)

        self._file_model = EcuFileTableModel()
        self._file_table = QTableView()
        self._file_table.setModel(self._file_model)
        self._file_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._file_table.setAlternatingRowColors(True)
        self._file_table.horizontalHeader().setStretchLastSection(True)
        self._file_table.doubleClicked.connect(lambda _i: self._open_hex_view())
        self._file_table.selectionModel().selectionChanged.connect(self._update_file_buttons)

        self._import_button = QPushButton("Importer un fichier ECU…")
        self._import_button.clicked.connect(self._import_file_dialog)
        self._import_button.setEnabled(False)
        self._compare_button = QPushButton("Comparer (2 fichiers)")
        self._compare_button.clicked.connect(self._compare_selected)
        self._compare_button.setEnabled(False)
        self._hex_button = QPushButton("Vue hexadécimale")
        self._hex_button.clicked.connect(self._open_hex_view)
        self._hex_button.setEnabled(False)

        buttons = QHBoxLayout()
        buttons.addWidget(self._import_button)
        buttons.addWidget(self._compare_button)
        buttons.addWidget(self._hex_button)
        buttons.addStretch()

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self._details_label)
        layout.addLayout(buttons)
        layout.addWidget(self._file_table)

        dock = QDockWidget("Dossier véhicule", self)
        dock.setObjectName("dock_details")
        dock.setWidget(container)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _build_log_dock(self) -> None:
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(2000)

        self._log_handler = QtLogHandler()
        self._log_handler.record_emitted.connect(self._log_view.appendPlainText)
        logging.getLogger().addHandler(self._log_handler)

        dock = QDockWidget("Journal", self)
        dock.setObjectName("dock_log")
        dock.setWidget(self._log_view)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)

    def _build_actions(self) -> None:
        file_menu = self.menuBar().addMenu("&Fichier")
        vehicle_menu = self.menuBar().addMenu("&Véhicule")
        help_menu = self.menuBar().addMenu("&Aide")

        new_vehicle = QAction("Nouveau véhicule…", self)
        new_vehicle.setShortcut(QKeySequence("Ctrl+N"))
        new_vehicle.triggered.connect(self._new_vehicle)
        vehicle_menu.addAction(new_vehicle)

        edit_vehicle = QAction("Modifier le véhicule…", self)
        edit_vehicle.setShortcut(QKeySequence("F2"))
        edit_vehicle.triggered.connect(self._edit_vehicle)
        vehicle_menu.addAction(edit_vehicle)

        delete_vehicle = QAction("Supprimer le véhicule", self)
        delete_vehicle.triggered.connect(self._delete_vehicle)
        vehicle_menu.addAction(delete_vehicle)

        import_action = QAction("Importer un fichier ECU…", self)
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_action.triggered.connect(self._import_file_dialog)
        file_menu.addAction(import_action)

        search_action = QAction("Rechercher", self)
        search_action.setShortcut(QKeySequence("Ctrl+F"))
        search_action.triggered.connect(lambda: self._search.setFocus())
        file_menu.addAction(search_action)

        file_menu.addSeparator()
        quit_action = QAction("Quitter", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        about = QAction(f"À propos de {APP_NAME}", self)
        about.triggered.connect(
            lambda: QMessageBox.about(
                self,
                APP_NAME,
                f"<b>{APP_NAME} {__version__}</b><br>"
                "Assistant professionnel de calibration ECU.",
            )
        )
        help_menu.addAction(about)

    def _connect_events(self) -> None:
        self._bridge = EventBridge(
            self._context.bus,
            [VehicleCreated, VehicleUpdated, VehicleDeleted, EcuFileImported],
            parent=self,
        )
        self._bridge.event_received.connect(self._on_domain_event)

    # -------------------------------------------------------------- events --

    def _on_domain_event(self, event: object) -> None:
        if isinstance(event, VehicleCreated | VehicleUpdated | VehicleDeleted):
            self.refresh_vehicles()
        if isinstance(event, EcuFileImported):
            self._refresh_files()
            note = " (déjà connu, dédupliqué)" if event.deduplicated else ""
            self.statusBar().showMessage(
                f"Importé : {event.ecu_file.original_filename}{note}", 8000
            )

    def refresh_vehicles(self) -> None:
        selected = self._current_vehicle.id if self._current_vehicle else None
        vehicles = (
            self._context.vehicles.search(self._search.text())
            if self._search.text().strip()
            else self._context.vehicles.list_all()
        )
        self._vehicle_model.set_vehicles(vehicles)
        if selected is not None:
            for row, vehicle in enumerate(vehicles):
                if vehicle.id == selected:
                    self._vehicle_list.setCurrentIndex(self._vehicle_model.index(row))
                    return
        self._current_vehicle = None
        self._show_vehicle_details(None)

    def _on_search(self, _text: str) -> None:
        self.refresh_vehicles()

    def _on_vehicle_selected(self, current, _previous) -> None:
        vehicle = self._vehicle_model.vehicle_at(current.row()) if current.isValid() else None
        self._current_vehicle = vehicle
        self._show_vehicle_details(vehicle)

    def _show_vehicle_details(self, vehicle: VehicleDto | None) -> None:
        self._import_button.setEnabled(vehicle is not None)
        if vehicle is None:
            self._details_label.setText("Sélectionnez un véhicule.")
            self._file_model.set_files([])
            self._update_file_buttons()
            return
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
        self._details_label.setText("".join(rows))
        self._refresh_files()

    def _refresh_files(self) -> None:
        if self._current_vehicle is None:
            self._file_model.set_files([])
        else:
            self._file_model.set_files(
                self._context.ecu_files.list_for_vehicle(self._current_vehicle.id)
            )
        self._update_file_buttons()

    def _selected_files(self) -> list[EcuFileDto]:
        rows = {index.row() for index in self._file_table.selectionModel().selectedRows()}
        files = [self._file_model.file_at(row) for row in sorted(rows)]
        return [f for f in files if f is not None]

    def _update_file_buttons(self, *_args) -> None:
        selected = self._selected_files()
        self._compare_button.setEnabled(len(selected) == 2)
        self._hex_button.setEnabled(len(selected) == 1)

    # ------------------------------------------------------------- actions --

    def _new_vehicle(self) -> None:
        dialog = VehicleDialog(self)
        if dialog.exec() and (data := dialog.vehicle_input()):
            try:
                self._context.vehicles.create(data)
            except Exception as exc:
                show_error(self, f"Création impossible : {exc}")

    def _edit_vehicle(self) -> None:
        if self._current_vehicle is None:
            return
        dialog = VehicleDialog(self, vehicle=self._current_vehicle)
        if dialog.exec() and (data := dialog.vehicle_input()):
            try:
                self._context.vehicles.update(self._current_vehicle.id, data)
            except Exception as exc:
                show_error(self, f"Mise à jour impossible : {exc}")

    def _delete_vehicle(self) -> None:
        if self._current_vehicle is None:
            return
        answer = QMessageBox.question(
            self,
            "Supprimer le véhicule",
            f"Supprimer « {self._current_vehicle.display_name} » et tous ses projets ?\n"
            "Les fichiers ECU importés restent conservés dans la bibliothèque.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._context.vehicles.delete(self._current_vehicle.id)

    def _import_file_dialog(self) -> None:
        if self._current_vehicle is None:
            QMessageBox.information(
                self, "Import", "Sélectionnez d'abord le véhicule concerné."
            )
            return
        paths, _filter = QFileDialog.getOpenFileNames(
            self,
            "Importer des fichiers ECU",
            "",
            "Fichiers binaires (*.bin *.ori *.mod *.hex *.frf *.dat);;Tous les fichiers (*)",
        )
        for path in paths:
            self._import_path(Path(path))

    def _import_path(self, path: Path) -> None:
        if self._current_vehicle is None:
            return
        vehicle_id = self._current_vehicle.id
        service = self._context.ecu_files
        self.statusBar().showMessage(f"Import de {path.name}…")
        run_in_background(
            lambda: service.import_file(
                path, vehicle_id=vehicle_id, kind=EcuFileKind.UNKNOWN
            ),
            on_done=lambda _dto: None,  # EcuFileImported event refreshes the UI
            on_error=lambda message: show_error(self, f"Import échoué : {message}"),
        )

    def _compare_selected(self) -> None:
        selected = self._selected_files()
        if len(selected) != 2:
            return
        file_a, file_b = selected
        service = self._context.ecu_files
        self.statusBar().showMessage("Comparaison en cours…")

        def on_done(result: object) -> None:
            self.statusBar().showMessage("Comparaison terminée", 5000)
            DiffResultDialog(
                file_a.original_filename, file_b.original_filename, result, self
            ).exec()

        run_in_background(
            lambda: service.compare(file_a.id, file_b.id),
            on_done=on_done,
            on_error=lambda message: show_error(self, f"Comparaison échouée : {message}"),
        )

    def _open_hex_view(self) -> None:
        selected = self._selected_files()
        if len(selected) != 1:
            return
        file = selected[0]
        service = self._context.ecu_files

        def on_done(data: object) -> None:
            assert isinstance(data, bytes)
            model = HexTableModel()
            model.set_data(data)
            view = QTableView()
            view.setModel(model)
            view.setFont(self.font())
            view.horizontalHeader().setDefaultSectionSize(32)
            view.horizontalHeader().setStretchLastSection(True)
            view.verticalHeader().setDefaultSectionSize(22)
            index = self._tabs.addTab(view, file.original_filename)
            self._tabs.setCurrentIndex(index)

        run_in_background(
            lambda: service.read_content(file.id),
            on_done=on_done,
            on_error=lambda message: show_error(self, f"Lecture échouée : {message}"),
        )

    def _close_tab(self, index: int) -> None:
        if index != 0:  # welcome tab stays
            self._tabs.removeTab(index)

    # --------------------------------------------------------- drag & drop --

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and self._current_vehicle is not None:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self._import_path(Path(url.toLocalFile()))
        event.acceptProposedAction()

    # ------------------------------------------------------------- layout --

    def _settings(self) -> QSettings:
        return QSettings(APP_NAME, APP_NAME)

    def _restore_layout(self) -> None:
        if not self._context.config.ui.restore_layout:
            return
        settings = self._settings()
        geometry = settings.value("main/geometry")
        state = settings.value("main/state")
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
        if isinstance(state, QByteArray):
            self.restoreState(state)

    def closeEvent(self, event: QCloseEvent) -> None:
        settings = self._settings()
        settings.setValue("main/geometry", self.saveGeometry())
        settings.setValue("main/state", self.saveState())
        logging.getLogger().removeHandler(self._log_handler)
        self._bridge.detach()
        super().closeEvent(event)
