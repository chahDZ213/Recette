"""HTML report builders.

Pure functions from DTOs to a self-contained HTML string. The markup sticks to
a Qt-rich-text-compatible subset (tables, headings, inline styles) so it looks
right both in a browser and when rendered to PDF by ``reporting.pdf``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape

from calforge import APP_NAME, __version__
from calforge.analysis.diff import DiffResult
from calforge.labels import (
    ENTRY_TYPE_LABELS,
    KIND_LABELS,
    STATUS_LABELS,
)
from calforge.services.dto import (
    AnnotationDto,
    EcuFileDto,
    HistoryEntryDto,
    MapCandidateDto,
    ProjectDto,
    VehicleDto,
)

_STYLE = """
body { font-family: 'Segoe UI', Arial, sans-serif; color: #1c1f24; font-size: 13px; }
h1 { font-size: 22px; margin: 0 0 2px 0; }
h2 { font-size: 16px; border-bottom: 2px solid #3d8bfd; padding-bottom: 3px;
     margin-top: 22px; color: #1a4f9c; }
.sub { color: #6b7280; font-size: 12px; margin-bottom: 4px; }
table { border-collapse: collapse; width: 100%; margin-top: 6px; }
th, td { border: 1px solid #d0d5dd; padding: 5px 8px; text-align: left;
         vertical-align: top; }
th { background: #eef2f7; }
.muted { color: #6b7280; }
.tag { font-weight: bold; }
.disclaimer { margin-top: 26px; color: #6b7280; font-style: italic; font-size: 11px;
              border-top: 1px solid #d0d5dd; padding-top: 8px; }
"""

_DISCLAIMER = (
    "Document généré automatiquement par CalForge à partir des données du projet. "
    "Les hypothèses (cartographies non validées, mesures interprétées) ne sont pas "
    "des certitudes et doivent être vérifiées avant toute intervention."
)


@dataclass(frozen=True, slots=True)
class VehicleReportData:
    vehicle: VehicleDto
    projects: list[ProjectDto]
    history: list[HistoryEntryDto]
    files: list[EcuFileDto]
    validated_maps: dict[int, list[MapCandidateDto]]  # file id -> validated maps


def _document(title: str, body: str) -> str:
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{escape(title)}</title><style>{_STYLE}</style></head><body>"
        f"<h1>{escape(title)}</h1>"
        f"<div class='sub'>{escape(APP_NAME)} {escape(__version__)} — généré le {generated}</div>"
        f"{body}"
        f"<div class='disclaimer'>{escape(_DISCLAIMER)}</div>"
        "</body></html>"
    )


def _table(headers: Iterable[str], rows: Iterable[Iterable[str]]) -> str:
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{cell}</td>" for cell in row)  # cells pre-escaped
        body_rows.append(f"<tr>{cells}</tr>")
    if not body_rows:
        return "<p class='muted'>(aucun)</p>"
    return f"<table><tr>{head}</tr>{''.join(body_rows)}</table>"


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("o", "Kio", "Mio", "Gio"):
        if value < 1024 or unit == "Gio":
            return f"{value:.0f} {unit}" if unit == "o" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} o"


def render_vehicle_report(data: VehicleReportData) -> str:
    v = data.vehicle
    identity_rows = [
        ("Marque / modèle", escape(v.display_name)),
        ("VIN", escape(v.vin or "—")),
        ("Immatriculation", escape(v.license_plate or "—")),
        ("Code moteur", escape(v.engine_code or "—")),
        ("Type d'ECU", escape(v.ecu_type or "—")),
    ]
    identity = _table(("Champ", "Valeur"), identity_rows)

    projects = _table(
        ("Projet", "Statut", "Créé le", "Description"),
        [
            (
                escape(p.name),
                escape(STATUS_LABELS[p.status]),
                p.created_at.strftime("%Y-%m-%d"),
                escape(p.description or "—"),
            )
            for p in data.projects
        ],
    )

    history = _table(
        ("Date", "Type", "Titre", "Détails"),
        [
            (
                e.occurred_at.strftime("%Y-%m-%d %H:%M"),
                escape(ENTRY_TYPE_LABELS[e.entry_type]),
                escape(e.title),
                escape(e.content or "—"),
            )
            for e in data.history
        ],
    )

    file_rows = []
    for f in data.files:
        maps = data.validated_maps.get(f.id, [])
        maps_label = (
            "<br>".join(
                f"{escape(m.name or 'sans nom')} (0x{m.offset:X}, {escape(m.shape_label)})"
                for m in maps
            )
            or "<span class='muted'>—</span>"
        )
        file_rows.append(
            (
                escape(f.original_filename),
                escape(KIND_LABELS[f.kind]),
                _human_size(f.size_bytes),
                f"<span class='muted'>{escape(f.sha256[:16])}…</span>",
                maps_label,
            )
        )
    files = _table(
        ("Fichier", "Type", "Taille", "SHA-256", "Cartographies validées"), file_rows
    )

    body = (
        "<h2>Identité</h2>" + identity
        + (f"<p>{escape(v.notes)}</p>" if v.notes else "")
        + "<h2>Projets</h2>" + projects
        + "<h2>Historique</h2>" + history
        + "<h2>Fichiers ECU</h2>" + files
    )
    return _document(f"Dossier véhicule — {v.display_name}", body)


def render_comparison_report(
    file_a: EcuFileDto,
    file_b: EcuFileDto,
    result: DiffResult,
    candidates: list[MapCandidateDto],
) -> str:
    summary = (
        "Les deux fichiers sont strictement identiques."
        if result.identical
        else f"{result.total_changed_bytes} octet(s) modifié(s) dans "
        f"{len(result.regions)} zone(s)."
    )
    meta = _table(
        ("", "Fichier A", "Fichier B"),
        [
            ("Nom", escape(file_a.original_filename), escape(file_b.original_filename)),
            ("Taille", _human_size(file_a.size_bytes), _human_size(file_b.size_bytes)),
            (
                "SHA-256",
                f"<span class='muted'>{escape(file_a.sha256[:16])}…</span>",
                f"<span class='muted'>{escape(file_b.sha256[:16])}…</span>",
            ),
        ],
    )

    region_rows = []
    for region in result.regions:
        covering = [
            c for c in candidates if not (region.end <= c.offset or region.offset >= c.end)
        ]
        names = (
            ", ".join(escape(c.name or f"@0x{c.offset:X}") for c in covering)
            or "<span class='muted'>—</span>"
        )
        region_rows.append(
            (
                f"0x{region.offset:X}",
                f"0x{region.end:X}",
                str(region.changed_bytes),
                names,
            )
        )
    regions = _table(
        ("Début", "Fin", "Octets modifiés", "Cartographies touchées"), region_rows
    )

    body = (
        f"<p class='tag'>{escape(summary)}</p>"
        + "<h2>Fichiers comparés</h2>" + meta
        + "<h2>Zones de différences</h2>" + regions
    )
    title = f"Comparaison — {file_a.original_filename} ⟷ {file_b.original_filename}"
    return _document(title, body)


def render_annotation_index(file: EcuFileDto, annotations: list[AnnotationDto]) -> str:
    rows = [
        (
            f"0x{a.offset:X}",
            str(a.length),
            "Favori" if a.kind.value == "bookmark" else "Note",
            escape(a.title),
            escape(a.comment or "—"),
        )
        for a in annotations
    ]
    body = "<h2>Annotations & favoris</h2>" + _table(
        ("Offset", "Longueur", "Type", "Titre", "Commentaire"), rows
    )
    return _document(f"Annotations — {file.original_filename}", body)
