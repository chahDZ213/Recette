"""Vehicle management service."""

from __future__ import annotations

import logging

from sqlalchemy import or_, select

from calforge.core.events import EventBus
from calforge.data.database import Database
from calforge.data.models import Vehicle
from calforge.services.dto import VehicleDto, VehicleInput
from calforge.services.events import VehicleCreated, VehicleDeleted, VehicleUpdated

logger = logging.getLogger(__name__)


class VehicleNotFoundError(LookupError):
    pass


class VehicleService:
    def __init__(self, database: Database, bus: EventBus) -> None:
        self._db = database
        self._bus = bus

    def create(self, data: VehicleInput) -> VehicleDto:
        with self._db.session() as session:
            vehicle = Vehicle(**data.model_dump())
            session.add(vehicle)
            session.flush()
            dto = VehicleDto.model_validate(vehicle)
        logger.info("Created vehicle #%d %s", dto.id, dto.display_name)
        self._bus.publish(VehicleCreated(vehicle=dto))
        return dto

    def update(self, vehicle_id: int, data: VehicleInput) -> VehicleDto:
        with self._db.session() as session:
            vehicle = session.get(Vehicle, vehicle_id)
            if vehicle is None:
                raise VehicleNotFoundError(vehicle_id)
            for key, value in data.model_dump().items():
                setattr(vehicle, key, value)
            session.flush()
            dto = VehicleDto.model_validate(vehicle)
        self._bus.publish(VehicleUpdated(vehicle=dto))
        return dto

    def delete(self, vehicle_id: int) -> None:
        with self._db.session() as session:
            vehicle = session.get(Vehicle, vehicle_id)
            if vehicle is None:
                raise VehicleNotFoundError(vehicle_id)
            session.delete(vehicle)
        logger.info("Deleted vehicle #%d", vehicle_id)
        self._bus.publish(VehicleDeleted(vehicle_id=vehicle_id))

    def get(self, vehicle_id: int) -> VehicleDto:
        with self._db.session() as session:
            vehicle = session.get(Vehicle, vehicle_id)
            if vehicle is None:
                raise VehicleNotFoundError(vehicle_id)
            return VehicleDto.model_validate(vehicle)

    def list_all(self) -> list[VehicleDto]:
        with self._db.session() as session:
            rows = session.scalars(select(Vehicle).order_by(Vehicle.make, Vehicle.model))
            return [VehicleDto.model_validate(v) for v in rows]

    def search(self, text: str) -> list[VehicleDto]:
        """Instant search across the main identifying fields."""
        pattern = f"%{text.strip()}%"
        if pattern == "%%":
            return self.list_all()
        with self._db.session() as session:
            stmt = (
                select(Vehicle)
                .where(
                    or_(
                        Vehicle.make.ilike(pattern),
                        Vehicle.model.ilike(pattern),
                        Vehicle.vin.ilike(pattern),
                        Vehicle.license_plate.ilike(pattern),
                        Vehicle.engine_code.ilike(pattern),
                        Vehicle.ecu_type.ilike(pattern),
                    )
                )
                .order_by(Vehicle.make, Vehicle.model)
            )
            return [VehicleDto.model_validate(v) for v in session.scalars(stmt)]
