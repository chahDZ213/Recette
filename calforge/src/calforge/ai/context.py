"""Factual context builder.

Assembles an ``AiContext`` from the application services. This is the single
point where product data becomes AI input, and it is deliberately strict:
only measured facts and already-scored hypotheses cross the boundary. No
provider ever touches a service or a raw file directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from calforge.ai.base import AiContext, ContextFact, ContextHypothesis
from calforge.data.models import MapCandidateStatus
from calforge.labels import ENTRY_TYPE_LABELS, KIND_LABELS

if TYPE_CHECKING:
    from calforge.services.analysis import AnalysisService
    from calforge.services.annotations import AnnotationService
    from calforge.services.ecufiles import EcuFileService
    from calforge.services.history import HistoryService
    from calforge.services.projects import ProjectService
    from calforge.services.vehicles import VehicleService


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("o", "Kio", "Mio", "Gio"):
        if value < 1024 or unit == "Gio":
            return f"{value:.0f} {unit}" if unit == "o" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} o"


class ContextBuilder:
    def __init__(
        self,
        ecu_files: EcuFileService,
        analysis: AnalysisService,
        annotations: AnnotationService,
        vehicles: VehicleService,
        projects: ProjectService,
        history: HistoryService,
    ) -> None:
        self._files = ecu_files
        self._analysis = analysis
        self._annotations = annotations
        self._vehicles = vehicles
        self._projects = projects
        self._history = history

    # --------------------------------------------------------------- file --

    def file_context(self, file_id: int) -> AiContext:
        file = self._files.get(file_id)
        candidates = self._analysis.list_candidates(file_id)
        annotations = self._annotations.list_for_file(file_id)

        facts = [
            ContextFact("Nom du fichier", file.original_filename),
            ContextFact("Taille", _human_size(file.size_bytes)),
            ContextFact("Type", KIND_LABELS[file.kind]),
            ContextFact("Empreinte SHA-256", file.sha256),
        ]
        if file.vehicle_label:
            facts.append(ContextFact("Véhicule", file.vehicle_label))
        if file.parent_label:
            facts.append(ContextFact("Version dérivée de", file.parent_label))
        for key, value in file.identified_facts.items():
            facts.append(ContextFact(f"Mesure : {key}", str(value)))

        validated = [c for c in candidates if c.status == MapCandidateStatus.VALIDATED]
        proposed = [c for c in candidates if c.status == MapCandidateStatus.PROPOSED]
        facts.append(
            ContextFact(
                "Cartographies",
                f"{len(validated)} validée(s), {len(proposed)} proposée(s)",
            )
        )
        for candidate in validated:
            label = candidate.name or f"carte @0x{candidate.offset:X}"
            facts.append(
                ContextFact(
                    f"Carte validée « {label} »",
                    f"offset 0x{candidate.offset:X}, {candidate.shape_label}",
                )
            )
        facts.append(ContextFact("Annotations", str(len(annotations))))

        hypotheses = [
            ContextHypothesis(h.statement, h.confidence, h.rationale)
            for h in file.hypotheses
        ]
        hypotheses.extend(
            ContextHypothesis(
                f"La zone @0x{c.offset:X} ({c.shape_label}) est la carte "
                f"« {c.name or 'sans nom'} »",
                c.confidence,
                c.rationale,
            )
            for c in proposed
        )
        return AiContext(
            subject=f"Fichier ECU « {file.original_filename} »",
            facts=tuple(facts),
            hypotheses=tuple(hypotheses),
        )

    # ------------------------------------------------------------ compare --

    def compare_context(self, file_id_a: int, file_id_b: int) -> AiContext:
        file_a = self._files.get(file_id_a)
        file_b = self._files.get(file_id_b)
        result = self._files.compare(file_id_a, file_id_b)
        candidates = self._analysis.list_candidates(file_id_a)

        facts = [
            ContextFact("Fichier A", file_a.original_filename),
            ContextFact("Fichier B", file_b.original_filename),
            ContextFact("Taille A", _human_size(file_a.size_bytes)),
            ContextFact("Taille B", _human_size(file_b.size_bytes)),
        ]
        if result.identical:
            facts.append(ContextFact("Résultat", "fichiers strictement identiques"))
        else:
            facts.append(
                ContextFact(
                    "Différences",
                    f"{result.total_changed_bytes} octet(s) dans "
                    f"{len(result.regions)} zone(s)",
                )
            )
        notes: list[str] = []
        for region in result.regions[:20]:
            covering = [
                c
                for c in candidates
                if not (region.end <= c.offset or region.offset >= c.end)
            ]
            location = ""
            if covering:
                names = ", ".join(c.name or f"@0x{c.offset:X}" for c in covering)
                location = f" (touche : {names})"
            notes.append(
                f"Zone 0x{region.offset:X}–0x{region.end:X} : "
                f"{region.changed_bytes} octet(s){location}"
            )
        return AiContext(
            subject=f"Comparaison « {file_a.original_filename} » ⟷ "
            f"« {file_b.original_filename} »",
            facts=tuple(facts),
            notes=tuple(notes),
        )

    # ---------------------------------------------------------- candidate --

    def candidate_context(self, candidate_id: int) -> AiContext:
        candidate = self._analysis.get_candidate(candidate_id)
        facts = [
            ContextFact("Cartographie", candidate.name or "(sans nom)"),
            ContextFact("Offset", f"0x{candidate.offset:X}"),
            ContextFact("Dimensions", candidate.shape_label),
            ContextFact("Statut", candidate.status.value),
        ]
        hypotheses = (
            ContextHypothesis(
                f"Cette zone est une cartographie ({candidate.shape_label})",
                candidate.confidence,
                candidate.rationale,
            ),
        )
        return AiContext(
            subject=f"Cartographie « {candidate.name or 'sans nom'} »",
            facts=tuple(facts),
            hypotheses=hypotheses,
        )

    # ------------------------------------------------------------ vehicle --

    def vehicle_context(self, vehicle_id: int) -> AiContext:
        vehicle = self._vehicles.get(vehicle_id)
        projects = self._projects.list_for_vehicle(vehicle_id)
        files = self._files.list_for_vehicle(vehicle_id)
        history = self._history.list_for_vehicle(vehicle_id)

        facts = [ContextFact("Véhicule", vehicle.display_name)]
        for label, value in (
            ("VIN", vehicle.vin),
            ("Code moteur", vehicle.engine_code),
            ("Type d'ECU", vehicle.ecu_type),
        ):
            if value:
                facts.append(ContextFact(label, value))
        facts.append(ContextFact("Projets", str(len(projects))))
        facts.append(ContextFact("Fichiers ECU", str(len(files))))
        facts.append(ContextFact("Entrées d'historique", str(len(history))))

        notes = [
            f"{entry.occurred_at:%Y-%m-%d} · {ENTRY_TYPE_LABELS[entry.entry_type]} : "
            f"{entry.title}"
            for entry in history[:8]
        ]
        return AiContext(
            subject=f"Véhicule « {vehicle.display_name} »",
            facts=tuple(facts),
            notes=tuple(notes),
        )
