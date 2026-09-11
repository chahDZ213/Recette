"""Data transfer objects exchanged between services and the UI/plugins.

DTOs are immutable snapshots. They validate user input (a UI form binds to
``VehicleInput``) and shield the presentation layer from the ORM.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from calforge.data.models import (
    AnnotationKind,
    AttachmentCategory,
    EcuFileKind,
    HistoryEntryType,
    MapCandidateStatus,
    ProjectStatus,
)


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
    parent_file_id: int | None = None
    sha256: str
    size_bytes: int
    original_filename: str
    kind: EcuFileKind
    format_name: str | None
    identified_facts: dict
    hypotheses: tuple[HypothesisDto, ...]
    notes: str
    created_at: datetime
    #: Denormalised display labels, filled by the service while the ORM
    #: session is still open (the UI must never trigger lazy loads).
    vehicle_label: str | None = None
    parent_label: str | None = None


class AttachmentDto(_Dto):
    id: int
    vehicle_id: int
    sha256: str
    size_bytes: int
    original_filename: str
    category: AttachmentCategory
    notes: str
    created_at: datetime


class HistoryEntryInput(BaseModel):
    vehicle_id: int
    project_id: int | None = None
    entry_type: HistoryEntryType = HistoryEntryType.NOTE
    title: str = Field(min_length=1, max_length=200)
    content: str = ""
    occurred_at: datetime

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class HistoryEntryDto(_Dto):
    id: int
    vehicle_id: int
    project_id: int | None
    entry_type: HistoryEntryType
    title: str
    content: str
    occurred_at: datetime
    created_at: datetime


class AnnotationInput(BaseModel):
    ecu_file_id: int
    offset: int = Field(ge=0)
    length: int = Field(default=1, ge=1)
    kind: AnnotationKind = AnnotationKind.ANNOTATION
    title: str = Field(min_length=1, max_length=200)
    comment: str = ""

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AnnotationDto(_Dto):
    id: int
    ecu_file_id: int
    offset: int
    length: int
    kind: AnnotationKind
    title: str
    comment: str
    created_at: datetime

    @property
    def end(self) -> int:
        return self.offset + self.length


class DefinitionSourceDto(_Dto):
    id: int
    name: str
    description: str
    map_count: int = 0
    created_at: datetime


class MapDefinitionDto(_Dto):
    id: int
    source_id: int
    name: str
    category: str
    offset: int
    rows: int
    cols: int
    element_size: int
    endianness: str
    factor: float
    value_offset: float
    unit: str
    description: str

    @property
    def shape_label(self) -> str:
        bits = 8 * self.element_size
        suffix = f" {self.endianness.upper()}" if self.endianness else ""
        return f"{self.rows}×{self.cols} · {bits} bits{suffix}"


class MapCandidateDto(_Dto):
    id: int
    ecu_file_id: int
    definition_id: int | None = None
    offset: int
    rows: int
    cols: int
    element_size: int
    endianness: str
    confidence: float
    rationale: str
    status: MapCandidateStatus
    name: str
    created_at: datetime

    @property
    def byte_length(self) -> int:
        return self.rows * self.cols * self.element_size

    @property
    def end(self) -> int:
        return self.offset + self.byte_length

    @property
    def shape_label(self) -> str:
        bits = 8 * self.element_size
        suffix = f" {self.endianness.upper()}" if self.endianness else ""
        return f"{self.rows}×{self.cols} · {bits} bits{suffix}"
