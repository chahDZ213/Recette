from __future__ import annotations

from pathlib import Path

import pytest

from calforge.app import ApplicationContext
from calforge.data.models import ProjectStatus
from calforge.services.dto import ProjectInput, VehicleInput
from calforge.services.events import EcuFileImported, VehicleCreated
from calforge.services.vehicles import VehicleNotFoundError


def make_vehicle(context: ApplicationContext, **overrides):
    data = {"make": "Volkswagen", "model": "Golf GTI", "year": 2019} | overrides
    return context.vehicles.create(VehicleInput(**data))


class TestVehicles:
    def test_create_and_get(self, context: ApplicationContext) -> None:
        created = make_vehicle(context, vin="wvwzzz1kzam000001")
        fetched = context.vehicles.get(created.id)
        assert fetched.display_name == "Volkswagen Golf GTI 2019"
        assert fetched.vin == "WVWZZZ1KZAM000001"  # normalised to uppercase

    def test_create_publishes_event(self, context: ApplicationContext) -> None:
        received = []
        context.bus.subscribe(VehicleCreated, received.append)
        make_vehicle(context)
        assert len(received) == 1

    def test_update(self, context: ApplicationContext) -> None:
        vehicle = make_vehicle(context)
        updated = context.vehicles.update(
            vehicle.id,
            VehicleInput(make="Volkswagen", model="Golf R", year=2020, ecu_type="MG1CS111"),
        )
        assert updated.model == "Golf R"
        assert updated.ecu_type == "MG1CS111"

    def test_delete_then_get_raises(self, context: ApplicationContext) -> None:
        vehicle = make_vehicle(context)
        context.vehicles.delete(vehicle.id)
        with pytest.raises(VehicleNotFoundError):
            context.vehicles.get(vehicle.id)

    def test_search_matches_multiple_fields(self, context: ApplicationContext) -> None:
        make_vehicle(context, make="BMW", model="M340i", ecu_type="MG1")
        make_vehicle(context, make="Audi", model="S3", ecu_type="Simos 19")
        assert [v.make for v in context.vehicles.search("simos")] == ["Audi"]
        assert [v.make for v in context.vehicles.search("M340")] == ["BMW"]
        assert len(context.vehicles.search("")) == 2

    def test_input_validation_rejects_blank_make(self) -> None:
        with pytest.raises(ValueError):
            VehicleInput(make="  ", model="Golf")

    def test_duplicate_vin_raises_friendly_error(self, context: ApplicationContext) -> None:
        from calforge.services.vehicles import DuplicateVinError

        make_vehicle(context, vin="WVWZZZ1KZAM000001")
        with pytest.raises(DuplicateVinError) as exc_info:
            make_vehicle(context, model="Golf R", vin="wvwzzz1kzam000001")  # same VIN, normalised
        assert "existe déjà" in str(exc_info.value)
        # State stays consistent: only the first vehicle exists.
        assert len(context.vehicles.list_all()) == 1

    def test_duplicate_vin_on_update_raises_friendly_error(
        self, context: ApplicationContext
    ) -> None:
        from calforge.services.vehicles import DuplicateVinError

        make_vehicle(context, vin="VIN000000000000A1")
        second = make_vehicle(context, model="Polo", vin="VIN000000000000B2")
        with pytest.raises(DuplicateVinError):
            context.vehicles.update(
                second.id, VehicleInput(make="VW", model="Polo", vin="VIN000000000000A1")
            )


class TestProjects:
    def test_create_and_list_for_vehicle(self, context: ApplicationContext) -> None:
        vehicle = make_vehicle(context)
        project = context.projects.create(
            ProjectInput(vehicle_id=vehicle.id, name="Stage 1", description="Base 245ch")
        )
        assert project.status == ProjectStatus.ACTIVE
        projects = context.projects.list_for_vehicle(vehicle.id)
        assert [p.name for p in projects] == ["Stage 1"]


class TestEcuFiles:
    def test_import_records_facts_and_hypotheses(
        self, context: ApplicationContext, sample_bin: Path
    ) -> None:
        vehicle = make_vehicle(context)
        dto = context.ecu_files.import_file(sample_bin, vehicle_id=vehicle.id)

        assert dto.size_bytes == sample_bin.stat().st_size
        assert dto.identified_facts["size_bytes"] == dto.size_bytes
        assert dto.format_name == "generic-binary"
        for hypothesis in dto.hypotheses:
            assert 0.0 <= hypothesis.confidence <= 1.0
            assert hypothesis.rationale

    def test_import_twice_deduplicates_blob(
        self, context: ApplicationContext, sample_bin: Path
    ) -> None:
        events = []
        context.bus.subscribe(EcuFileImported, events.append)
        vehicle = make_vehicle(context)

        first = context.ecu_files.import_file(sample_bin, vehicle_id=vehicle.id)
        second = context.ecu_files.import_file(sample_bin, vehicle_id=vehicle.id)

        assert first.sha256 == second.sha256
        assert first.id != second.id  # two records, one blob
        assert [e.deduplicated for e in events] == [False, True]

    def test_read_content_roundtrip(
        self, context: ApplicationContext, sample_bin: Path
    ) -> None:
        dto = context.ecu_files.import_file(sample_bin)
        assert context.ecu_files.read_content(dto.id) == sample_bin.read_bytes()

    def test_compare_two_imports(
        self, context: ApplicationContext, sample_bin: Path, tmp_path: Path
    ) -> None:
        modified_path = tmp_path / "modified.bin"
        payload = bytearray(sample_bin.read_bytes())
        payload[0x100] ^= 0xFF
        modified_path.write_bytes(payload)

        original = context.ecu_files.import_file(sample_bin)
        modified = context.ecu_files.import_file(modified_path)

        result = context.ecu_files.compare(original.id, modified.id)
        assert result.total_changed_bytes == 1
        assert result.regions[0].offset == 0x100
