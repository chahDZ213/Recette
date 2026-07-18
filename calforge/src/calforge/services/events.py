"""Domain events published by the application services."""

from __future__ import annotations

from dataclasses import dataclass

from calforge.core.events import Event
from calforge.services.dto import EcuFileDto, ProjectDto, VehicleDto


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
