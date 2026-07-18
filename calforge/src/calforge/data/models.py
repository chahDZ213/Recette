"""SQLAlchemy ORM models.

Rules for this module:

- Models never leave the persistence layer: services map them to DTOs
  (``calforge.services.dto``) so ORM sessions stay short-lived and the UI is
  decoupled from the schema.
- Every schema change requires a new Alembic revision in
  ``calforge/data/migrations/versions``. Never edit an applied revision.
- Enumerated values are stored as strings (validated by the DTO layer) so
  adding a member never needs a migration.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    DELIVERED = "delivered"
    ARCHIVED = "archived"


class EcuFileKind(StrEnum):
    ORIGINAL = "original"
    MODIFIED = "modified"
    UNKNOWN = "unknown"


class AttachmentCategory(StrEnum):
    PHOTO = "photo"
    DOCUMENT = "document"
    INVOICE = "invoice"
    OTHER = "other"


class HistoryEntryType(StrEnum):
    INTERVENTION = "intervention"
    DIAGNOSTIC = "diagnostic"
    ROAD_TEST = "road_test"
    LOG = "log"
    CALIBRATION = "calibration"
    NOTE = "note"


class Vehicle(TimestampMixin, Base):
    """A customer vehicle. The central record everything else links to."""

    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    make: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    year: Mapped[int | None] = mapped_column(Integer)
    vin: Mapped[str | None] = mapped_column(String(17), unique=True)
    license_plate: Mapped[str | None] = mapped_column(String(20))
    engine_code: Mapped[str | None] = mapped_column(String(50))
    ecu_type: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str] = mapped_column(Text, default="")

    projects: Mapped[list[Project]] = relationship(
        back_populates="vehicle", cascade="all, delete-orphan"
    )
    ecu_files: Mapped[list[EcuFile]] = relationship(back_populates="vehicle")
    attachments: Mapped[list[Attachment]] = relationship(
        back_populates="vehicle", cascade="all, delete-orphan"
    )
    history_entries: Mapped[list[HistoryEntry]] = relationship(
        back_populates="vehicle", cascade="all, delete-orphan"
    )


class Project(TimestampMixin, Base):
    """A unit of calibration work on one vehicle (e.g. "Stage 1")."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default=ProjectStatus.ACTIVE.value)
    description: Mapped[str] = mapped_column(Text, default="")

    vehicle: Mapped[Vehicle] = relationship(back_populates="projects")
    ecu_files: Mapped[list[EcuFile]] = relationship(back_populates="project")


class EcuFile(TimestampMixin, Base):
    """Metadata for one imported ECU binary.

    The binary content itself lives in the content-addressed blob store keyed
    by ``sha256``; several EcuFile rows may point to the same blob (same dump
    imported under different projects), which is how deduplication surfaces
    to the user without ever deleting their records.

    ``identified_facts`` only ever contains information *proven* from the file
    content. ``hypotheses`` contains scored guesses with rationale — the two
    are never mixed (see ADR-0004).
    """

    __tablename__ = "ecu_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL")
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL")
    )
    #: Versioning: a modified calibration points to the file it derives from.
    parent_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("ecu_files.id", ondelete="SET NULL")
    )
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    original_filename: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(20), default=EcuFileKind.UNKNOWN.value)
    format_name: Mapped[str | None] = mapped_column(String(100))
    identified_facts: Mapped[dict] = mapped_column(JSON, default=dict)
    hypotheses: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")

    vehicle: Mapped[Vehicle | None] = relationship(back_populates="ecu_files")
    project: Mapped[Project | None] = relationship(back_populates="ecu_files")
    parent: Mapped[EcuFile | None] = relationship(
        remote_side="EcuFile.id", back_populates="derivatives"
    )
    derivatives: Mapped[list[EcuFile]] = relationship(back_populates="parent")


class Attachment(TimestampMixin, Base):
    """A document attached to a vehicle (photo, invoice, report…).

    Content lives in the same content-addressed blob store as ECU binaries
    (ADR-0003): deduplicated, immutable, integrity-checked.
    """

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    original_filename: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(30), default=AttachmentCategory.OTHER.value)
    notes: Mapped[str] = mapped_column(Text, default="")

    vehicle: Mapped[Vehicle] = relationship(back_populates="attachments")


class HistoryEntry(TimestampMixin, Base):
    """One event in a vehicle's unified timeline (ADR-0006): mechanical
    intervention, diagnostic, road test, datalog, calibration step or note."""

    __tablename__ = "history_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"))
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL")
    )
    entry_type: Mapped[str] = mapped_column(String(30), default=HistoryEntryType.NOTE.value)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    vehicle: Mapped[Vehicle] = relationship(back_populates="history_entries")
