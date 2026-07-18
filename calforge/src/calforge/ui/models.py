"""Qt item models over service DTOs.

Models hold immutable DTO snapshots and are refreshed wholesale from service
calls; they never touch the database themselves. The hex model computes rows
lazily from an in-memory buffer, so multi-MB dumps cost nothing to display.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractListModel, QAbstractTableModel, QModelIndex, Qt

from calforge.services.dto import (
    AttachmentDto,
    EcuFileDto,
    HistoryEntryDto,
    ProjectDto,
    VehicleDto,
)
from calforge.ui.labels import (
    CATEGORY_LABELS,
    ENTRY_TYPE_LABELS,
    KIND_LABELS,
    STATUS_LABELS,
)

VEHICLE_ID_ROLE = Qt.ItemDataRole.UserRole + 1


class VehicleListModel(QAbstractListModel):
    def __init__(self) -> None:
        super().__init__()
        self._vehicles: list[VehicleDto] = []

    def set_vehicles(self, vehicles: list[VehicleDto]) -> None:
        self.beginResetModel()
        self._vehicles = vehicles
        self.endResetModel()

    def vehicle_at(self, row: int) -> VehicleDto | None:
        return self._vehicles[row] if 0 <= row < len(self._vehicles) else None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._vehicles)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        vehicle = self.vehicle_at(index.row())
        if vehicle is None:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return vehicle.display_name
        if role == Qt.ItemDataRole.ToolTipRole:
            details = [vehicle.display_name]
            if vehicle.vin:
                details.append(f"VIN : {vehicle.vin}")
            if vehicle.ecu_type:
                details.append(f"ECU : {vehicle.ecu_type}")
            return "\n".join(details)
        if role == VEHICLE_ID_ROLE:
            return vehicle.id
        return None


class _DtoTableModel[T](QAbstractTableModel):
    """Base for read-only tables over a list of DTOs."""

    HEADERS: tuple[str, ...] = ()

    def __init__(self) -> None:
        super().__init__()
        self._items: list[T] = []

    def set_items(self, items: list[T]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def item_at(self, row: int) -> T | None:
        return self._items[row] if 0 <= row < len(self._items) else None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        item = self.item_at(index.row())
        if item is None:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return self.display(item, index.column())
        if role == Qt.ItemDataRole.ToolTipRole:
            return self.tooltip(item)
        return None

    def display(self, item: T, column: int) -> str | None:  # pragma: no cover - abstract
        raise NotImplementedError

    def tooltip(self, item: T) -> str | None:
        return None


class ProjectTableModel(_DtoTableModel[ProjectDto]):
    HEADERS = ("Projet", "Statut", "Créé le")

    def display(self, item: ProjectDto, column: int) -> str | None:
        if column == 0:
            return item.name
        if column == 1:
            return STATUS_LABELS[item.status]
        if column == 2:
            return item.created_at.strftime("%Y-%m-%d")
        return None

    def tooltip(self, item: ProjectDto) -> str | None:
        return item.description or None


class HistoryTableModel(_DtoTableModel[HistoryEntryDto]):
    HEADERS = ("Date", "Type", "Titre")

    def display(self, item: HistoryEntryDto, column: int) -> str | None:
        if column == 0:
            return item.occurred_at.strftime("%Y-%m-%d %H:%M")
        if column == 1:
            return ENTRY_TYPE_LABELS[item.entry_type]
        if column == 2:
            return item.title
        return None

    def tooltip(self, item: HistoryEntryDto) -> str | None:
        return item.content or None


class AttachmentTableModel(_DtoTableModel[AttachmentDto]):
    HEADERS = ("Fichier", "Catégorie", "Taille", "Ajouté le")

    def display(self, item: AttachmentDto, column: int) -> str | None:
        if column == 0:
            return item.original_filename
        if column == 1:
            return CATEGORY_LABELS[item.category]
        if column == 2:
            return _human_size(item.size_bytes)
        if column == 3:
            return item.created_at.strftime("%Y-%m-%d")
        return None

    def tooltip(self, item: AttachmentDto) -> str | None:
        return item.notes or None


class EcuLibraryTableModel(_DtoTableModel[EcuFileDto]):
    """Global ECU file library: every file, with vehicle and lineage."""

    HEADERS = ("Fichier", "Véhicule", "Type", "Version de", "Taille", "Format", "Importé le")

    def display(self, item: EcuFileDto, column: int) -> str | None:
        if column == 0:
            return item.original_filename
        if column == 1:
            return item.vehicle_label or "—"
        if column == 2:
            return KIND_LABELS[item.kind]
        if column == 3:
            return item.parent_label or "—"
        if column == 4:
            return _human_size(item.size_bytes)
        if column == 5:
            return item.format_name or "—"
        if column == 6:
            return item.created_at.strftime("%Y-%m-%d %H:%M")
        return None

    def tooltip(self, item: EcuFileDto) -> str | None:
        lines = [f"SHA-256 : {item.sha256}"]
        if item.notes:
            lines.append(item.notes)
        return "\n".join(lines)


class EcuFileTableModel(QAbstractTableModel):
    HEADERS = ("Fichier", "Taille", "Type", "Version de", "Format", "SHA-256", "Importé le")

    def __init__(self) -> None:
        super().__init__()
        self._files: list[EcuFileDto] = []

    def set_files(self, files: list[EcuFileDto]) -> None:
        self.beginResetModel()
        self._files = files
        self.endResetModel()

    def file_at(self, row: int) -> EcuFileDto | None:
        return self._files[row] if 0 <= row < len(self._files) else None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._files)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        file = self.file_at(index.row())
        if file is None or role != Qt.ItemDataRole.DisplayRole:
            return None
        column = index.column()
        if column == 0:
            return file.original_filename
        if column == 1:
            return _human_size(file.size_bytes)
        if column == 2:
            return KIND_LABELS[file.kind]
        if column == 3:
            return file.parent_label or "—"
        if column == 4:
            return file.format_name or "—"
        if column == 5:
            return file.sha256[:12] + "…"
        if column == 6:
            return file.created_at.strftime("%Y-%m-%d %H:%M")
        return None


class HexTableModel(QAbstractTableModel):
    """Read-only hexadecimal view: 16 bytes per row + ASCII column."""

    BYTES_PER_ROW = 16

    def __init__(self) -> None:
        super().__init__()
        self._data = b""

    def set_data(self, data: bytes) -> None:
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return (len(self._data) + self.BYTES_PER_ROW - 1) // self.BYTES_PER_ROW

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        # 16 byte columns + ASCII rendering column
        return 0 if parent.isValid() else self.BYTES_PER_ROW + 1

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return "ASCII" if section == self.BYTES_PER_ROW else f"{section:X}"
        return f"{section * self.BYTES_PER_ROW:08X}"

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        row_start = index.row() * self.BYTES_PER_ROW
        chunk = self._data[row_start : row_start + self.BYTES_PER_ROW]
        if index.column() == self.BYTES_PER_ROW:
            return "".join(chr(b) if 0x20 <= b < 0x7F else "·" for b in chunk)
        offset = index.column()
        if offset >= len(chunk):
            return ""
        return f"{chunk[offset]:02X}"


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("o", "Kio", "Mio", "Gio"):
        if value < 1024 or unit == "Gio":
            return f"{value:.0f} {unit}" if unit == "o" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} o"
