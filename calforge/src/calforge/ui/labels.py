"""French display labels for domain enums.

Kept in one module so the future i18n pass (v1.0) only touches this file and
the ``tr()``-wrapped literals.
"""

from __future__ import annotations

from calforge.data.models import (
    AttachmentCategory,
    EcuFileKind,
    HistoryEntryType,
    ProjectStatus,
)

KIND_LABELS: dict[EcuFileKind, str] = {
    EcuFileKind.ORIGINAL: "Original",
    EcuFileKind.MODIFIED: "Modifié",
    EcuFileKind.UNKNOWN: "Inconnu",
}

STATUS_LABELS: dict[ProjectStatus, str] = {
    ProjectStatus.ACTIVE: "Actif",
    ProjectStatus.DELIVERED: "Livré",
    ProjectStatus.ARCHIVED: "Archivé",
}

CATEGORY_LABELS: dict[AttachmentCategory, str] = {
    AttachmentCategory.PHOTO: "Photo",
    AttachmentCategory.DOCUMENT: "Document",
    AttachmentCategory.INVOICE: "Facture",
    AttachmentCategory.OTHER: "Autre",
}

ENTRY_TYPE_LABELS: dict[HistoryEntryType, str] = {
    HistoryEntryType.INTERVENTION: "Intervention",
    HistoryEntryType.DIAGNOSTIC: "Diagnostic",
    HistoryEntryType.ROAD_TEST: "Essai routier",
    HistoryEntryType.LOG: "Datalog",
    HistoryEntryType.CALIBRATION: "Calibration",
    HistoryEntryType.NOTE: "Note",
}
