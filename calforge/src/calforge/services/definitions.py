"""Definition sources (map packs): import/export, matching, application.

Applying a matched pack to a file creates *candidates* in the same store as
the heuristic detector (ADR-0007/0008): even a definition can be wrong for a
given file, so results remain proposals carrying a confidence derived from
the match strength (exact SHA-256 > byte signature > file size) and a
rationale naming the source — human validation stays in the loop.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import func, select

from calforge.analysis import packbuilder
from calforge.core.events import EventBus
from calforge.data.database import Database
from calforge.data.models import (
    DefinitionMatcher,
    DefinitionSource,
    MapCandidateRecord,
    MapCandidateStatus,
    MapDefinition,
    MatcherKind,
)
from calforge.packs import (
    PACK_FORMAT,
    Pack,
    PackMap,
    SignatureMatcher,
)
from calforge.services.dto import (
    DefinitionSourceDto,
    EcuFileDto,
    MapCandidateDto,
    MapDefinitionDto,
)
from calforge.services.ecufiles import EcuFileService
from calforge.services.events import (
    DefinitionSourceDeleted,
    DefinitionSourceImported,
    MapCandidatesRefreshed,
)

logger = logging.getLogger(__name__)

#: Confidence of candidates created from a definition, by match strength.
MATCH_CONFIDENCE = {
    MatcherKind.SHA256: 0.95,
    MatcherKind.SIGNATURE: 0.85,
    MatcherKind.SIZE: 0.60,
}

_MATCH_LABELS = {
    MatcherKind.SHA256: "empreinte SHA-256 exacte",
    MatcherKind.SIGNATURE: "signature d'octets",
    MatcherKind.SIZE: "taille de fichier (indice faible)",
}


class DefinitionSourceNotFoundError(LookupError):
    pass


class PackImportError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SourceMatch:
    source: DefinitionSourceDto
    matched_by: MatcherKind


class DefinitionService:
    def __init__(self, database: Database, ecu_files: EcuFileService, bus: EventBus) -> None:
        self._db = database
        self._files = ecu_files
        self._bus = bus

    # ------------------------------------------------------------ sources --

    def import_pack(self, path: Path) -> DefinitionSourceDto:
        """Import a ``*.calpack.json`` file as a new definition source."""
        try:
            pack = Pack.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise PackImportError(f"Pack invalide ({path.name}) : {exc}") from exc
        return self._persist_pack(pack)

    def _persist_pack(self, pack: Pack) -> DefinitionSourceDto:
        """Store a validated Pack as a new definition source (shared by import
        and the automatic pack builders)."""
        with self._db.session() as session:
            existing = session.scalar(
                select(DefinitionSource).where(DefinitionSource.name == pack.name)
            )
            if existing is not None:
                raise PackImportError(
                    f"Une source nommée « {pack.name} » existe déjà. "
                    "Supprimez-la d'abord ou renommez le pack."
                )
            source = DefinitionSource(name=pack.name, description=pack.description)
            session.add(source)
            session.flush()
            for matcher in pack.matchers:
                payload = matcher.model_dump(exclude={"kind"})
                session.add(
                    DefinitionMatcher(source_id=source.id, kind=matcher.kind, payload=payload)
                )
            for map_def in pack.maps:
                session.add(MapDefinition(source_id=source.id, **map_def.model_dump()))
            dto = self._source_dto(source, map_count=len(pack.maps))

        logger.info("Persisted pack %r (%d maps)", pack.name, len(pack.maps))
        self._bus.publish(DefinitionSourceImported(source=dto))
        return dto

    def export_pack(self, source_id: int, target: Path) -> Path:
        """Write a source back to the open pack format (lossless roundtrip)."""
        with self._db.session() as session:
            source = session.get(DefinitionSource, source_id)
            if source is None:
                raise DefinitionSourceNotFoundError(source_id)
            matchers = [
                {"kind": m.kind, **m.payload} for m in source.matchers
            ]
            maps = [
                PackMap.model_validate(d, from_attributes=True).model_dump()
                for d in source.definitions
            ]
            pack = Pack.model_validate(
                {
                    "format": PACK_FORMAT,
                    "name": source.name,
                    "description": source.description,
                    "matchers": matchers,
                    "maps": maps,
                }
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            pack.model_dump_json(indent=2), encoding="utf-8"
        )
        logger.info("Exported source #%d to %s", source_id, target)
        return target

    def list_sources(self) -> list[DefinitionSourceDto]:
        with self._db.session() as session:
            counts = dict(
                session.execute(
                    select(MapDefinition.source_id, func.count(MapDefinition.id)).group_by(
                        MapDefinition.source_id
                    )
                ).all()
            )
            sources = session.scalars(
                select(DefinitionSource).order_by(DefinitionSource.name)
            )
            return [self._source_dto(s, map_count=counts.get(s.id, 0)) for s in sources]

    def delete_source(self, source_id: int) -> None:
        with self._db.session() as session:
            source = session.get(DefinitionSource, source_id)
            if source is None:
                raise DefinitionSourceNotFoundError(source_id)
            session.delete(source)
        logger.info("Deleted definition source #%d", source_id)
        self._bus.publish(DefinitionSourceDeleted(source_id=source_id))

    def list_definitions(self, source_id: int) -> list[MapDefinitionDto]:
        with self._db.session() as session:
            stmt = (
                select(MapDefinition)
                .where(MapDefinition.source_id == source_id)
                .order_by(MapDefinition.offset)
            )
            return [MapDefinitionDto.model_validate(d) for d in session.scalars(stmt)]

    def get_definition(self, definition_id: int) -> MapDefinitionDto | None:
        with self._db.session() as session:
            record = session.get(MapDefinition, definition_id)
            return MapDefinitionDto.model_validate(record) if record else None

    @staticmethod
    def _source_dto(source: DefinitionSource, *, map_count: int) -> DefinitionSourceDto:
        dto = DefinitionSourceDto.model_validate(source)
        return dto.model_copy(update={"map_count": map_count})

    # ----------------------------------------------------- pack building --

    def build_pack_from_comparison(
        self,
        original_id: int,
        modified_ids: list[int],
        *,
        name: str | None = None,
    ) -> DefinitionSourceDto:
        """Learn a Map Pack by comparing an original to modified file(s).

        The regions that a real tune changed and that also look like maps
        become high-confidence definitions; changed-only regions are included
        best-effort. The pack matches the original by SHA-256 + size, so
        applying it later re-proposes the same maps for human validation.
        """
        if not modified_ids:
            raise ValueError("Sélectionnez au moins un fichier modifié à comparer.")
        original = self._files.get(original_id)
        original_bytes = self._files.read_content(original_id)
        modified_bytes = [self._files.read_content(mid) for mid in modified_ids]

        discovered = packbuilder.discover_maps_from_comparison(original_bytes, modified_bytes)
        if not discovered:
            raise PackImportError(
                "Aucune différence exploitable : les fichiers sont identiques ou "
                "les zones modifiées sont trop petites pour être des cartographies."
            )

        pack_name = name or f"Pack appris — {original.original_filename}"
        maps = []
        for m in discovered:
            kind = "détectée+modifiée" if m.from_geometry else "zone modifiée"
            maps.append(
                PackMap(
                    name=f"Carte {kind} @0x{m.offset:X}",
                    category="apprise",
                    offset=m.offset,
                    rows=m.rows,
                    cols=m.cols,
                    element_size=m.element_size,
                    endianness=m.endianness,
                    factor=1.0,
                    value_offset=0.0,
                    unit="",
                    description=(
                        f"Découverte par comparaison ({m.changed_bytes} octet(s) "
                        f"modifié(s), confiance {m.confidence:.0%}). "
                        + ("Forme de cartographie confirmée. " if m.from_geometry else "")
                        + "À vérifier avant toute utilisation."
                    ),
                )
            )
        pack = Pack.model_validate(
            {
                "format": PACK_FORMAT,
                "name": pack_name,
                "description": (
                    f"Pack généré automatiquement en comparant "
                    f"« {original.original_filename} » à {len(modified_ids)} fichier(s) "
                    "modifié(s). Chaque cartographie doit être vérifiée."
                ),
                "matchers": [
                    {"kind": "sha256", "sha256": original.sha256},
                    {"kind": "size", "size": original.size_bytes},
                ],
                "maps": [m.model_dump() for m in maps],
            }
        )
        logger.info(
            "Built pack from comparison of #%d vs %s: %d map(s)",
            original_id, modified_ids, len(maps),
        )
        return self._persist_pack(pack)

    def build_pack_from_validated(
        self, file_id: int, *, name: str | None = None
    ) -> DefinitionSourceDto:
        """Turn a file's human-validated maps into a reusable Map Pack.

        This captures the user's own validation work so a matching file later
        gets the same maps proposed automatically — the app learning from its
        operator."""
        file = self._files.get(file_id)
        with self._db.session() as session:
            validated = session.scalars(
                select(MapCandidateRecord).where(
                    MapCandidateRecord.ecu_file_id == file_id,
                    MapCandidateRecord.status == MapCandidateStatus.VALIDATED.value,
                )
            ).all()
            rows = [
                {
                    "name": v.name or f"Carte @0x{v.offset:X}",
                    "category": "validée",
                    "offset": v.offset,
                    "rows": v.rows,
                    "cols": v.cols,
                    "element_size": v.element_size,
                    "endianness": v.endianness,
                    "factor": 1.0,
                    "value_offset": 0.0,
                    "unit": "",
                    "description": "Cartographie validée par l'utilisateur.",
                }
                for v in validated
            ]
        if not rows:
            raise PackImportError(
                "Aucune cartographie validée sur ce fichier. Validez d'abord des "
                "cartographies dans la vue d'analyse."
            )
        pack = Pack.model_validate(
            {
                "format": PACK_FORMAT,
                "name": name or f"Pack validé — {file.original_filename}",
                "description": (
                    f"Pack construit à partir des cartographies validées de "
                    f"« {file.original_filename} »."
                ),
                "matchers": [
                    {"kind": "sha256", "sha256": file.sha256},
                    {"kind": "size", "size": file.size_bytes},
                ],
                "maps": rows,
            }
        )
        logger.info("Built pack from %d validated map(s) of file #%d", len(rows), file_id)
        return self._persist_pack(pack)

    # ----------------------------------------------------------- matching --

    def match_sources_for_file(self, file_id: int) -> list[SourceMatch]:
        """Sources applying to a file, each with its strongest match kind."""
        file = self._files.get(file_id)
        data: bytes | None = None  # lazily read, only if a signature matcher exists
        matches: list[SourceMatch] = []
        with self._db.session() as session:
            for source in session.scalars(select(DefinitionSource)):
                best: MatcherKind | None = None
                for matcher in source.matchers:
                    kind = MatcherKind(matcher.kind)
                    if kind == MatcherKind.SIGNATURE and data is None:
                        data = self._files.read_content(file_id)
                    if not self._matcher_applies(kind, matcher.payload, file, data):
                        continue
                    if best is None or MATCH_CONFIDENCE[kind] > MATCH_CONFIDENCE[best]:
                        best = kind
                if best is not None:
                    map_count = session.scalar(
                        select(func.count(MapDefinition.id)).where(
                            MapDefinition.source_id == source.id
                        )
                    )
                    matches.append(
                        SourceMatch(
                            source=self._source_dto(source, map_count=map_count or 0),
                            matched_by=best,
                        )
                    )
        matches.sort(key=lambda m: MATCH_CONFIDENCE[m.matched_by], reverse=True)
        return matches

    @staticmethod
    def _matcher_applies(
        kind: MatcherKind, payload: dict, file: EcuFileDto, data: bytes | None
    ) -> bool:
        if kind == MatcherKind.SHA256:
            return payload.get("sha256", "").lower() == file.sha256.lower()
        if kind == MatcherKind.SIZE:
            return payload.get("size") == file.size_bytes
        if kind == MatcherKind.SIGNATURE and data is not None:
            matcher = SignatureMatcher(kind="signature", **payload)
            end = matcher.offset + len(matcher.pattern)
            return data[matcher.offset : end] == matcher.pattern
        return False

    # -------------------------------------------------------- application --

    def apply_definitions(self, file_id: int) -> list[MapCandidateDto]:
        """Create candidates from every matching source's definitions.

        Refresh semantics mirror the heuristic detector: previously applied
        definition proposals are replaced, human-decided candidates survive
        untouched, and nothing may overlap a decided region.
        """
        matches = self.match_sources_for_file(file_id)
        file_size = self._files.get(file_id).size_bytes
        with self._db.session() as session:
            decided = session.scalars(
                select(MapCandidateRecord).where(
                    MapCandidateRecord.ecu_file_id == file_id,
                    MapCandidateRecord.status != MapCandidateStatus.PROPOSED.value,
                )
            ).all()
            decided_ranges = [
                (d.offset, d.offset + d.rows * d.cols * d.element_size) for d in decided
            ]
            for stale in session.scalars(
                select(MapCandidateRecord).where(
                    MapCandidateRecord.ecu_file_id == file_id,
                    MapCandidateRecord.status == MapCandidateStatus.PROPOSED.value,
                    MapCandidateRecord.definition_id.is_not(None),
                )
            ):
                session.delete(stale)

            created = 0
            for match in matches:
                confidence = MATCH_CONFIDENCE[match.matched_by]
                for definition in session.scalars(
                    select(MapDefinition).where(MapDefinition.source_id == match.source.id)
                ):
                    start = definition.offset
                    end = start + definition.rows * definition.cols * definition.element_size
                    if end > file_size:
                        # A definition that runs past EOF can never be decoded
                        # (the pack does not fit this file). Skip it instead of
                        # creating a broken candidate.
                        logger.warning(
                            "Définition « %s » (0x%X..0x%X) hors limites du fichier "
                            "#%d (%d o) — ignorée.",
                            definition.name, start, end, file_id, file_size,
                        )
                        continue
                    if any(not (end <= s or start >= e) for s, e in decided_ranges):
                        continue
                    session.add(
                        MapCandidateRecord(
                            ecu_file_id=file_id,
                            definition_id=definition.id,
                            offset=definition.offset,
                            rows=definition.rows,
                            cols=definition.cols,
                            element_size=definition.element_size,
                            endianness=definition.endianness,
                            confidence=confidence,
                            rationale=(
                                f"Définition « {definition.name} » du pack "
                                f"« {match.source.name} », correspondance par "
                                f"{_MATCH_LABELS[match.matched_by]}. "
                                "Vérifiez avant toute modification."
                            ),
                            name=definition.name,
                        )
                    )
                    created += 1

        logger.info(
            "Applied %d source(s) to file #%d (%d candidate(s))",
            len(matches),
            file_id,
            created,
        )
        with self._db.session() as session:
            stmt = (
                select(MapCandidateRecord)
                .where(MapCandidateRecord.ecu_file_id == file_id)
                .order_by(MapCandidateRecord.confidence.desc(), MapCandidateRecord.offset)
            )
            candidates = [MapCandidateDto.model_validate(c) for c in session.scalars(stmt)]
        self._bus.publish(
            MapCandidatesRefreshed(ecu_file_id=file_id, candidates=tuple(candidates))
        )
        return candidates
