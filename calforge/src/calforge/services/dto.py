"""Data transfer objects exchanged between services and the UI/plugins.

DTOs are immutable snapshots. They validate user input (a UI form binds to
``VehicleInput``) and shield the presentation layer from the ORM.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from calforge.data.models import EcuFileKind, ProjectStatus


class _Dto(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)


class VehicleInput(BaseModel):
    make: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    year: int | None = Field(default=None, ge=1900, le=2100)
    vin: str | None = Field(default=None, max_length=17)
    license_plate: str | None = Field(default=None, max_length=20)
    engine_code: str | None = Field(default=None, max_length=50)
    ecu_type: str | None = Field(default=None, max_length=100)
    notes: str = ""

    @field_validator("make", "model", mode="before")
    @classmethod
    def _strip_required(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("vin", "license_plate", "engine_code", "ecu_type", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("vin")
    @classmethod
    def _normalize_vin(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value


class VehicleDto(_Dto):
    id: int
    make: str
    model: str
    year: int | None
    vin: str | None
    license_plate: str | None
    engine_code: str | None
    ecu_type: str | None
    notes: str
    created_at: datetime
    updated_at: datetime

    @property
    def display_name(self) -> str:
        parts = [self.make, self.model]
        if self.year:
            parts.append(str(self.year))
        return " ".join(parts)


class ProjectInput(BaseModel):
    vehicle_id: int
    name: str = Field(min_length=1, max_length=200)
    status: ProjectStatus = ProjectStatus.ACTIVE
    description: str = ""


class ProjectDto(_Dto):
    id: int
    vehicle_id: int
    name: str
    status: ProjectStatus
    description: str
    created_at: datetime
    updated_at: datetime


class HypothesisDto(_Dto):
    statement: str
    confidence: float
    rationale: str


class EcuFileDto(_Dto):
    id: int
    vehicle_id: int | None
    project_id: int | None
    sha256: str
    size_bytes: int
    original_filename: str
    kind: EcuFileKind
    format_name: str | None
    identified_facts: dict
    hypotheses: tuple[HypothesisDto, ...]
    notes: str
    created_at: datetime
