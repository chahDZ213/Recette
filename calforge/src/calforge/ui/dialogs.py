"""Modal dialogs: vehicle/project/history forms, attachment metadata, diff summary."""

from __future__ import annotations

from datetime import UTC

from pydantic import ValidationError
from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from calforge.analysis.diff import DiffResult
from calforge.data.models import AttachmentCategory, HistoryEntryType, ProjectStatus
from calforge.services.dto import (
    HistoryEntryInput,
    ProjectDto,
    ProjectInput,
    VehicleDto,
    VehicleInput,
)
from calforge.ui.labels import CATEGORY_LABELS, ENTRY_TYPE_LABELS, STATUS_LABELS


class VehicleDialog(QDialog):
    """Create/edit form bound to ``VehicleInput`` — validation errors from the
    DTO are surfaced next to the form, so UI and business rules never drift."""

    def __init__(self, parent: QWidget | None = None, vehicle: VehicleDto | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nouveau véhicule" if vehicle is None else "Modifier le véhicule")
        self.setMinimumWidth(420)
        self._result: VehicleInput | None = None

        self._make = QLineEdit()
        self._model = QLineEdit()
        self._year = QSpinBox()
        self._year.setRange(0, 2100)
        self._year.setSpecialValueText("—")
        self._vin = QLineEdit()
        self._vin.setMaxLength(17)
        self._plate = QLineEdit()
        self._engine = QLineEdit()
        self._ecu = QLineEdit()
        self._notes = QTextEdit()
        self._notes.setAcceptRichText(False)
        self._error = QLabel()
        self._error.setStyleSheet("color: #e05561;")
        self._error.setWordWrap(True)
        self._error.hide()

        form = QFormLayout()
        form.addRow("Marque *", self._make)
        form.addRow("Modèle *", self._model)
        form.addRow("Année", self._year)
        form.addRow("VIN", self._vin)
        form.addRow("Immatriculation", self._plate)
        form.addRow("Code moteur", self._engine)
        form.addRow("Type d'ECU", self._ecu)
        form.addRow("Notes", self._notes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._error)
        layout.addWidget(buttons)

        if vehicle is not None:
            self._make.setText(vehicle.make)
            self._model.setText(vehicle.model)
            self._year.setValue(vehicle.year or 0)
            self._vin.setText(vehicle.vin or "")
            self._plate.setText(vehicle.license_plate or "")
            self._engine.setText(vehicle.engine_code or "")
            self._ecu.setText(vehicle.ecu_type or "")
            self._notes.setPlainText(vehicle.notes)

    def _on_accept(self) -> None:
        try:
            self._result = VehicleInput(
                make=self._make.text().strip(),
                model=self._model.text().strip(),
                year=self._year.value() or None,
                vin=self._vin.text(),
                license_plate=self._plate.text(),
                engine_code=self._engine.text(),
                ecu_type=self._ecu.text(),
                notes=self._notes.toPlainText(),
            )
        except ValidationError as exc:
            first = exc.errors()[0]
            field = ".".join(str(loc) for loc in first["loc"])
            self._error.setText(f"Champ « {field} » invalide : {first['msg']}")
            self._error.show()
            return
        self.accept()

    def vehicle_input(self) -> VehicleInput | None:
        return self._result


class ProjectDialog(QDialog):
    """Create/edit form for a calibration project."""

    def __init__(
        self,
        vehicle_id: int,
        parent: QWidget | None = None,
        project: ProjectDto | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nouveau projet" if project is None else "Modifier le projet")
        self.setMinimumWidth(420)
        self._vehicle_id = vehicle_id
        self._result: ProjectInput | None = None

        self._name = QLineEdit()
        self._status = QComboBox()
        for status in ProjectStatus:
            self._status.addItem(STATUS_LABELS[status], status)
        self._description = QTextEdit()
        self._description.setAcceptRichText(False)
        self._error = QLabel()
        self._error.setStyleSheet("color: #e05561;")
        self._error.hide()

        form = QFormLayout()
        form.addRow("Nom *", self._name)
        form.addRow("Statut", self._status)
        form.addRow("Description", self._description)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._error)
        layout.addWidget(buttons)

        if project is not None:
            self._name.setText(project.name)
            self._status.setCurrentIndex(list(ProjectStatus).index(project.status))
            self._description.setPlainText(project.description)

    def _on_accept(self) -> None:
        try:
            self._result = ProjectInput(
                vehicle_id=self._vehicle_id,
                name=self._name.text().strip(),
                status=self._status.currentData(),
                description=self._description.toPlainText(),
            )
        except ValidationError as exc:
            self._error.setText(f"Formulaire invalide : {exc.errors()[0]['msg']}")
            self._error.show()
            return
        self.accept()

    def project_input(self) -> ProjectInput | None:
        return self._result


class HistoryEntryDialog(QDialog):
    """Add an event to the vehicle timeline."""

    def __init__(self, vehicle_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nouvelle entrée d'historique")
        self.setMinimumWidth(460)
        self._vehicle_id = vehicle_id
        self._result: HistoryEntryInput | None = None

        self._type = QComboBox()
        for entry_type in HistoryEntryType:
            self._type.addItem(ENTRY_TYPE_LABELS[entry_type], entry_type)
        self._occurred = QDateTimeEdit(QDateTime.currentDateTime())
        self._occurred.setCalendarPopup(True)
        self._occurred.setDisplayFormat("yyyy-MM-dd HH:mm")
        self._title = QLineEdit()
        self._content = QTextEdit()
        self._content.setAcceptRichText(False)
        self._error = QLabel()
        self._error.setStyleSheet("color: #e05561;")
        self._error.hide()

        form = QFormLayout()
        form.addRow("Type", self._type)
        form.addRow("Date", self._occurred)
        form.addRow("Titre *", self._title)
        form.addRow("Détails", self._content)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._error)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        occurred = self._occurred.dateTime().toPython().replace(tzinfo=UTC)
        try:
            self._result = HistoryEntryInput(
                vehicle_id=self._vehicle_id,
                entry_type=self._type.currentData(),
                title=self._title.text(),
                content=self._content.toPlainText(),
                occurred_at=occurred,
            )
        except ValidationError as exc:
            self._error.setText(f"Formulaire invalide : {exc.errors()[0]['msg']}")
            self._error.show()
            return
        self.accept()

    def entry_input(self) -> HistoryEntryInput | None:
        return self._result


class AttachmentMetaDialog(QDialog):
    """Category + notes applied to files being attached to a vehicle."""

    def __init__(self, filenames: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ajouter des documents")
        self.setMinimumWidth(420)

        summary = QLabel(
            f"{len(filenames)} fichier(s) : " + ", ".join(filenames[:5])
            + ("…" if len(filenames) > 5 else "")
        )
        summary.setWordWrap(True)

        self._category = QComboBox()
        for category in AttachmentCategory:
            self._category.addItem(CATEGORY_LABELS[category], category)
        self._notes = QLineEdit()

        form = QFormLayout()
        form.addRow("Catégorie", self._category)
        form.addRow("Notes", self._notes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(summary)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def category(self) -> AttachmentCategory:
        return self._category.currentData()

    def notes(self) -> str:
        return self._notes.text().strip()


class DiffResultDialog(QDialog):
    """Summary of a byte-level comparison between two files."""

    def __init__(self, name_a: str, name_b: str, result: DiffResult, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Comparaison binaire")
        self.setMinimumSize(560, 420)

        layout = QVBoxLayout(self)
        if result.identical:
            summary = "Les deux fichiers sont strictement identiques."
        else:
            summary = (
                f"{result.total_changed_bytes} octet(s) modifié(s) "
                f"dans {len(result.regions)} zone(s)."
            )
        header = QLabel(f"<b>{name_a}</b> ⟷ <b>{name_b}</b><br>{summary}")
        header.setWordWrap(True)
        layout.addWidget(header)

        table = QTableWidget(len(result.regions), 4)
        table.setHorizontalHeaderLabels(["Début", "Fin", "Longueur", "Octets modifiés"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, region in enumerate(result.regions):
            for col, value in enumerate(
                (f"0x{region.offset:X}", f"0x{region.end:X}", str(region.length), str(region.changed_bytes))
            ):
                table.setItem(row, col, QTableWidgetItem(value))
        table.resizeColumnsToContents()
        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Fermer")
        buttons.rejected.connect(self.reject)
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)


def show_error(parent: QWidget | None, message: str) -> None:
    QMessageBox.critical(parent, "Erreur", message)
