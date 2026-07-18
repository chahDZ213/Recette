"""Calibration project management service."""

from __future__ import annotations

import logging

from sqlalchemy import select

from calforge.core.events import EventBus
from calforge.data.database import Database
from calforge.data.models import Project
from calforge.services.dto import ProjectDto, ProjectInput
from calforge.services.events import ProjectCreated, ProjectUpdated

logger = logging.getLogger(__name__)


class ProjectNotFoundError(LookupError):
    pass


class ProjectService:
    def __init__(self, database: Database, bus: EventBus) -> None:
        self._db = database
        self._bus = bus

    def create(self, data: ProjectInput) -> ProjectDto:
        with self._db.session() as session:
            project = Project(**data.model_dump(mode="json"))
            session.add(project)
            session.flush()
            dto = ProjectDto.model_validate(project)
        logger.info("Created project #%d %r", dto.id, dto.name)
        self._bus.publish(ProjectCreated(project=dto))
        return dto

    def update(self, project_id: int, data: ProjectInput) -> ProjectDto:
        with self._db.session() as session:
            project = session.get(Project, project_id)
            if project is None:
                raise ProjectNotFoundError(project_id)
            for key, value in data.model_dump(mode="json").items():
                setattr(project, key, value)
            session.flush()
            dto = ProjectDto.model_validate(project)
        self._bus.publish(ProjectUpdated(project=dto))
        return dto

    def get(self, project_id: int) -> ProjectDto:
        with self._db.session() as session:
            project = session.get(Project, project_id)
            if project is None:
                raise ProjectNotFoundError(project_id)
            return ProjectDto.model_validate(project)

    def list_for_vehicle(self, vehicle_id: int) -> list[ProjectDto]:
        with self._db.session() as session:
            stmt = (
                select(Project)
                .where(Project.vehicle_id == vehicle_id)
                .order_by(Project.created_at.desc())
            )
            return [ProjectDto.model_validate(p) for p in session.scalars(stmt)]
