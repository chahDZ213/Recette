"""Domain events published by the application services."""

from __future__ import annotations

from dataclasses import dataclass

from calforge.core.events import Event
from calforge.services.dto import (
    AnnotationDto,
    AttachmentDto,
    EcuFileDto,
    HistoryEntryDto,
    MapCandidateDto,
    ProjectDto,
    VehicleDto,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class VehicleCreated(Event):
    vehicle: VehicleDto


@dataclass(frozen=True, slots=True, kw_only=True)
class VehicleUpdated(Event):
    vehicle: VehicleDto


@dataclass(frozen=True, slots=True, kw_only=True)
class VehicleDeleted(Event):
    vehicle_id: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectCreated(Event):
    project: ProjectDto


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectUpdated(Event):
    project: ProjectDto


@dataclass(frozen=True, slots=True, kw_only=True)
class EcuFileImported(Event):
    ecu_file: EcuFileDto
    deduplicated: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class AttachmentAdded(Event):
    attachment: AttachmentDto


@dataclass(frozen=True, slots=True, kw_only=True)
class AttachmentDeleted(Event):
    attachment_id: int
    vehicle_id: int


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoryEntryAdded(Event):
    entry: HistoryEntryDto


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoryEntryDeleted(Event):
    entry_id: int
    vehicle_id: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AnnotationAdded(Event):
    annotation: AnnotationDto


@dataclass(frozen=True, slots=True, kw_only=True)
class AnnotationDeleted(Event):
    annotation_id: int
    ecu_file_id: int


@dataclass(frozen=True, slots=True, kw_only=True)
class MapCandidatesRefreshed(Event):
    ecu_file_id: int
    candidates: tuple[MapCandidateDto, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class MapCandidateUpdated(Event):
    candidate: MapCandidateDto
