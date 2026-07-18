"""Modal dialogs: vehicle form, diff summary."""

from __future__ import annotations

from pydantic import ValidationError
from PySide6.QtWidgets import (
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
from calforge.services.dto import VehicleDto, VehicleInput


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
        buttons.rejected.connect(self.reject)
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)


def show_error(parent: QWidget | None, message: str) -> None:
    QMessageBox.critical(parent, "Erreur", message)
