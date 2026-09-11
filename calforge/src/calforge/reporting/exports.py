"""CSV / JSON data exports (pure Python, Qt-free, testable)."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from calforge.labels import KIND_LABELS
from calforge.reporting.documents import VehicleReportData


def files_to_csv(files: list, get_vehicle_label=lambda f: f.vehicle_label or "") -> str:
    """Serialise a list of EcuFileDto to CSV text (spreadsheet-friendly)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["filename", "vehicle", "kind", "format", "size_bytes", "sha256", "imported_at"]
    )
    for f in files:
        writer.writerow(
            [
                f.original_filename,
                get_vehicle_label(f),
                KIND_LABELS[f.kind],
                f.format_name or "",
                f.size_bytes,
                f.sha256,
                f.created_at.isoformat(),
            ]
        )
    return buffer.getvalue()


def vehicle_to_dict(data: VehicleReportData) -> dict[str, Any]:
    """Structured, round-trippable snapshot of a vehicle folder."""
    v = data.vehicle
    return {
        "vehicle": {
            "make": v.make,
            "model": v.model,
            "year": v.year,
            "vin": v.vin,
            "license_plate": v.license_plate,
            "engine_code": v.engine_code,
            "ecu_type": v.ecu_type,
            "notes": v.notes,
        },
        "projects": [
            {"name": p.name, "status": p.status.value, "description": p.description}
            for p in data.projects
        ],
        "history": [
            {
                "occurred_at": e.occurred_at.isoformat(),
                "type": e.entry_type.value,
                "title": e.title,
                "content": e.content,
            }
            for e in data.history
        ],
        "files": [
            {
                "filename": f.original_filename,
                "kind": f.kind.value,
                "size_bytes": f.size_bytes,
                "sha256": f.sha256,
                "format": f.format_name,
                "validated_maps": [
                    {
                        "name": m.name,
                        "offset": m.offset,
                        "rows": m.rows,
                        "cols": m.cols,
                        "element_size": m.element_size,
                        "endianness": m.endianness,
                    }
                    for m in data.validated_maps.get(f.id, [])
                ],
            }
            for f in data.files
        ],
    }


def vehicle_to_json(data: VehicleReportData) -> str:
    return json.dumps(vehicle_to_dict(data), ensure_ascii=False, indent=2)
