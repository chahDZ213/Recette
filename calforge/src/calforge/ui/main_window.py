"""Main application window: dockable panels around a tabbed document area.

The window owns global chrome (menus, docks, status bar, log console, tabs)
and cross-panel operations (hex tabs, comparisons). Vehicle-scoped features
live in ``VehicleDetailsPanel``; the global file library in ``EcuLibraryPanel``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtGui import QAction, QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from calforge import APP_NAME, __version__
from calforge.app import ApplicationContext
from calforge.services.dto import EcuFileDto
from calforge.services.events import (
    AttachmentAdded,
    AttachmentDeleted,
    EcuFileImported,
    HistoryEntryAdded,
    HistoryEntryDeleted,
    ProjectCreated,
    ProjectUpdated,
    VehicleCreated,
    VehicleDeleted,
    VehicleUpdated,
)
from calforge.ui.dialogs import VehicleDialog, show_error
from calforge.ui.dispatch import EventBridge, QtLogHandler
from calforge.ui.models import VehicleListModel
from calforge.ui.panels.assistant import AssistantPanel
from calforge.ui.panels.library import EcuLibraryPanel
from calforge.ui.panels.mappacks import MapPackPanel
from calforge.ui.panels.vehicle_details import VehicleDetailsPanel
from calforge.ui.views.ecu_file_view import EcuFileView
from calforge.ui.views.hex_compare import HexCompareView

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, context: ApplicationContext) -> None:
        super().__init__()
        self._context = context
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1480, 900)
        self.setAcceptDrops(True)
        self.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks | QMainWindow.DockOption.AllowNestedDocks
        )

        self._build_central_area()
        self._build_vehicle_dock()
        self._build_details_dock()
        self._build_assistant_dock()
        self._build_log_dock()
        self._build_actions()
        self._connect_events()
        self._tabs.currentChanged.connect(self._on_tab_changed)
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

        self._library = EcuLibraryPanel(self._context)
        self._library.hex_requested.connect(self._open_hex_view)
        self._map_packs = MapPackPanel(self._context)

        self._tabs.addTab(welcome, "Bienvenue")
        self._tabs.addTab(self._library, "Bibliothèque ECU")
        self._tabs.addTab(self._map_packs, "Map Packs")
        bar = self._tabs.tabBar()
        self._permanent_tabs = 3
        for permanent in range(self._permanent_tabs):
            bar.setTabButton(permanent, bar.ButtonPosition.RightSide, None)
        self.setCentralWidget(self._tabs)

    def _build_vehicle_dock(self) -> None:
        self._vehicle_model = VehicleListModel()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Rechercher (marque, VIN, ECU…)")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(lambda _t: self.refresh_vehicles())

        self._vehicle_list = QListView()
        self._vehicle_list.setModel(self._vehicle_model)
        self._vehicle_list.setAlternatingRowColors(True)
        self._vehicle_list.selectionModel().currentChanged.connect(self._on_vehicle_selected)
        self._vehicle_list.doubleClicked.connect(lambda _i: self._edit_vehicle())

        container = QWidget()
        container.setMinimumWidth(230)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self._search)
        layout.addWidget(self._vehicle_list)

        self._vehicle_dock = QDockWidget("Véhicules", self)
        self._vehicle_dock.setObjectName("dock_vehicles")
        self._vehicle_dock.setWidget(container)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._vehicle_dock)

    def _build_details_dock(self) -> None:
        self._details = VehicleDetailsPanel(self._context)
        self._details.hex_requested.connect(self._open_hex_view)
        self._details.compare_requested.connect(self._compare_files)
        self._details.status_message.connect(self.statusBar().showMessage)

        self._details_dock = QDockWidget("Dossier véhicule", self)
        self._details_dock.setObjectName("dock_details")
        self._details_dock.setWidget(self._details)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._details_dock)

    def _build_assistant_dock(self) -> None:
        self._assistant = AssistantPanel(self._context)

        self._assistant_dock = QDockWidget("Assistant IA", self)
        self._assistant_dock.setObjectName("dock_assistant")
        self._assistant_dock.setWidget(self._assistant)
        # Share the right column vertically with the vehicle folder so both
        # stay visible (folder on top, assistant below).
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._assistant_dock)

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
        import_action.triggered.connect(self._details.open_import_dialog)
        file_menu.addAction(import_action)

        library_action = QAction("Bibliothèque ECU", self)
        library_action.setShortcut(QKeySequence("Ctrl+L"))
        library_action.triggered.connect(lambda: self._tabs.setCurrentIndex(1))
        file_menu.addAction(library_action)

        packs_action = QAction("Map Packs", self)
        packs_action.setShortcut(QKeySequence("Ctrl+M"))
        packs_action.triggered.connect(lambda: self._tabs.setCurrentIndex(2))
        file_menu.addAction(packs_action)

        assistant_action = QAction("Assistant IA", self)
        assistant_action.setShortcut(QKeySequence("Ctrl+J"))
        assistant_action.triggered.connect(self._show_assistant)
        file_menu.addAction(assistant_action)

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
            [
                VehicleCreated,
                VehicleUpdated,
                VehicleDeleted,
                ProjectCreated,
                ProjectUpdated,
                EcuFileImported,
                AttachmentAdded,
                AttachmentDeleted,
                HistoryEntryAdded,
                HistoryEntryDeleted,
            ],
            parent=self,
        )
        self._bridge.event_received.connect(self._on_domain_event)

    # -------------------------------------------------------------- events --

    def _on_domain_event(self, event: object) -> None:
        if isinstance(event, VehicleCreated | VehicleUpdated | VehicleDeleted):
            self.refresh_vehicles()
        elif isinstance(event, ProjectCreated | ProjectUpdated):
            self._details.refresh_projects()
        elif isinstance(event, EcuFileImported):
            self._details.refresh_files()
            self._library.refresh()
            note = " (déjà connu, dédupliqué)" if event.deduplicated else ""
            self.statusBar().showMessage(
                f"Importé : {event.ecu_file.original_filename}{note}", 8000
            )
        elif isinstance(event, AttachmentAdded | AttachmentDeleted):
            self._details.refresh_documents()
        elif isinstance(event, HistoryEntryAdded | HistoryEntryDeleted):
            self._details.refresh_history()

    def refresh_vehicles(self) -> None:
        current = self._details.current_vehicle
        selected = current.id if current else None
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
                    self._set_current_vehicle(vehicle)
                    return
        self._set_current_vehicle(None)

    def _on_vehicle_selected(self, current, _previous) -> None:
        vehicle = self._vehicle_model.vehicle_at(current.row()) if current.isValid() else None
        self._set_current_vehicle(vehicle)

    def _set_current_vehicle(self, vehicle) -> None:
        self._details.set_vehicle(vehicle)
        self._assistant.set_vehicle(vehicle)

    def _on_tab_changed(self, _index: int) -> None:
        """Point the assistant at the ECU file of the active analysis tab."""
        widget = self._tabs.currentWidget()
        self._assistant.set_active_file(
            widget.ecu_file if isinstance(widget, EcuFileView) else None
        )

    def _show_assistant(self) -> None:
        self._assistant_dock.show()
        self._assistant_dock.raise_()

    # ------------------------------------------------------------- actions --

    def _new_vehicle(self) -> None:
        dialog = VehicleDialog(self)
        if dialog.exec() and (data := dialog.vehicle_input()):
            try:
                self._context.vehicles.create(data)
            except Exception as exc:
                show_error(self, f"Création impossible : {exc}")

    def _edit_vehicle(self) -> None:
        vehicle = self._details.current_vehicle
        if vehicle is None:
            return
        dialog = VehicleDialog(self, vehicle=vehicle)
        if dialog.exec() and (data := dialog.vehicle_input()):
            try:
                self._context.vehicles.update(vehicle.id, data)
            except Exception as exc:
                show_error(self, f"Mise à jour impossible : {exc}")

    def _delete_vehicle(self) -> None:
        vehicle = self._details.current_vehicle
        if vehicle is None:
            return
        answer = QMessageBox.question(
            self,
            "Supprimer le véhicule",
            f"Supprimer « {vehicle.display_name} » et tous ses projets ?\n"
            "Les fichiers ECU importés restent conservés dans la bibliothèque.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._context.vehicles.delete(vehicle.id)

    def _compare_files(self, file_a: EcuFileDto, file_b: EcuFileDto) -> None:
        view = HexCompareView(self._context, file_a, file_b)
        title = f"{file_a.original_filename} ⟷ {file_b.original_filename}"
        index = self._tabs.addTab(view, title)
        self._tabs.setCurrentIndex(index)

    def _open_hex_view(self, file: EcuFileDto) -> None:
        view = EcuFileView(self._context, file)
        view.file_open_requested.connect(self._on_modified_file_created)
        index = self._tabs.addTab(view, file.original_filename)
        self._tabs.setCurrentIndex(index)

    def _on_modified_file_created(self, file: EcuFileDto) -> None:
        # A map edit produced a new modified file: refresh views and open it.
        self._details.refresh_files()
        self._library.refresh()
        self.statusBar().showMessage(f"Fichier modifié créé : {file.original_filename}", 8000)
        self._open_hex_view(file)

    def _close_tab(self, index: int) -> None:
        if index >= self._permanent_tabs:  # welcome/library/packs tabs stay
            self._tabs.removeTab(index)

    # --------------------------------------------------------- drag & drop --

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and self._details.current_vehicle is not None:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [
            Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()
        ]
        self._details.import_paths(paths)
        event.acceptProposedAction()

    # ------------------------------------------------------------- layout --

    def _settings(self) -> QSettings:
        return QSettings(APP_NAME, APP_NAME)

    def _restore_layout(self) -> None:
        restored = False
        if self._context.config.ui.restore_layout:
            settings = self._settings()
            geometry = settings.value("main/geometry")
            state = settings.value("main/state")
            if isinstance(geometry, QByteArray):
                self.restoreGeometry(geometry)
            if isinstance(state, QByteArray):
                restored = self.restoreState(state)
        if not restored:
            # First run: balanced default layout instead of Qt's minimal docks.
            self.resizeDocks(
                [self._vehicle_dock, self._details_dock],
                [260, 620],
                Qt.Orientation.Horizontal,
            )
            self.resizeDocks(
                [self._details_dock, self._assistant_dock],
                [440, 420],
                Qt.Orientation.Vertical,
            )

    def closeEvent(self, event: QCloseEvent) -> None:
        settings = self._settings()
        settings.setValue("main/geometry", self.saveGeometry())
        settings.setValue("main/state", self.saveState())
        logging.getLogger().removeHandler(self._log_handler)
        self._bridge.detach()
        super().closeEvent(event)
