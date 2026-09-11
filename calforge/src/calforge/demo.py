"""Seed demo data so a fresh install shows a realistic project immediately.

Invoked by ``python -m calforge --seed-demo`` (or the launcher's first run).
Idempotent: it does nothing if a demo vehicle already exists, so it is safe to
run repeatedly. Uses only public services — the same code path a user drives.
"""

from __future__ import annotations

import logging
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from calforge.app import ApplicationContext
from calforge.data.models import (
    AttachmentCategory,
    EcuFileKind,
    HistoryEntryType,
    MapCandidateStatus,
    ProjectStatus,
)
from calforge.services.dto import (
    HistoryEntryInput,
    ProjectInput,
    VehicleInput,
)

logger = logging.getLogger(__name__)

_DEMO_VIN = "WVWZZZAUZKW000123"


def _build_demo_dump() -> bytes:
    import numpy as np

    rng = np.random.default_rng(3)
    parts = [rng.integers(0, 256, size=0x8000, dtype=np.uint8).tobytes()]

    def planted(base: int, row_step: int, col_step: int, rows: int = 16, cols: int = 16) -> bytes:
        axis = np.arange(600, 600 + cols * 100, 100, dtype="<u2")
        r = np.arange(rows, dtype=np.float64)[:, None]
        c = np.arange(cols, dtype=np.float64)[None, :]
        return axis.tobytes() + (base + r * row_step + c * col_step).astype("<u2").tobytes()

    parts.append(planted(1000, 55, 30))
    parts.append(rng.integers(0, 256, size=0x2000, dtype=np.uint8).tobytes())
    parts.append(planted(2400, 40, 25, rows=12))
    parts.append(b"\xff" * 0x4000)
    return b"".join(parts)


def seed_demo(ctx: ApplicationContext) -> bool:
    """Populate demo data. Returns True if it seeded, False if already present."""
    for vehicle in ctx.vehicles.list_all():
        if vehicle.vin == _DEMO_VIN:
            logger.info("Demo data already present; skipping seed.")
            return False

    golf = ctx.vehicles.create(
        VehicleInput(
            make="Volkswagen",
            model="Golf 7 GTI",
            year=2019,
            vin=_DEMO_VIN,
            license_plate="AB-123-CD",
            engine_code="DKFA 2.0 TSI",
            ecu_type="Bosch MG1CS111 (démo)",
            notes="Données de démonstration. Objectif Stage 1 ~300 ch, boîte DSG d'origine.",
        )
    )
    ctx.vehicles.create(
        VehicleInput(make="BMW", model="M340i", year=2021, engine_code="B58B30")
    )
    ctx.vehicles.create(
        VehicleInput(make="Audi", model="RS3 8Y", year=2022, engine_code="DNWA 2.5 TFSI")
    )

    ctx.projects.create(
        ProjectInput(
            vehicle_id=golf.id,
            name="Stage 1",
            status=ProjectStatus.DELIVERED,
            description="Cartographie Stage 1 livrée.",
        )
    )
    ctx.projects.create(
        ProjectInput(vehicle_id=golf.id, name="Stage 2 + downpipe", description="En attente.")
    )

    base = datetime.now(UTC)
    for days, entry_type, title, content in [
        (30, HistoryEntryType.DIAGNOSTIC, "Lecture avant travaux", "Aucun code défaut."),
        (28, HistoryEntryType.INTERVENTION, "Filtre à air performance", "Installé."),
        (27, HistoryEntryType.CALIBRATION, "Flash Stage 1 v1", "Base sauvegardée avant écriture."),
        (26, HistoryEntryType.ROAD_TEST, "Essai de validation", "RAS, températures stables."),
        (2, HistoryEntryType.LOG, "Datalog autoroute", "Log 3e/4e rapport."),
    ]:
        ctx.history.add(
            HistoryEntryInput(
                vehicle_id=golf.id,
                entry_type=entry_type,
                title=title,
                content=content,
                occurred_at=base - timedelta(days=days),
            )
        )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        invoice = tmp_path / "facture-2026-0142.pdf"
        invoice.write_bytes(b"%PDF-1.7 demo invoice")
        ctx.attachments.add(golf.id, invoice, category=AttachmentCategory.INVOICE, notes="Stage 1")

        original = _build_demo_dump()
        orig_path = tmp_path / "golf7_gti_original.bin"
        orig_path.write_bytes(original)
        orig = ctx.ecu_files.import_file(orig_path, vehicle_id=golf.id, kind=EcuFileKind.ORIGINAL)

        modified = bytearray(original)
        for i in range(0x8020, 0x8160):  # tweak the first map
            modified[i] = min(0xFF, modified[i] + 16)
        mod_path = tmp_path / "golf7_gti_stage1.bin"
        mod_path.write_bytes(bytes(modified))
        ctx.ecu_files.import_file(
            mod_path, vehicle_id=golf.id, parent_file_id=orig.id
        )

    # Detect maps and validate one so the demo shows a fact + a hypothesis.
    candidates = ctx.analysis.detect_maps(orig.id)
    if candidates:
        ctx.analysis.set_candidate_status(
            candidates[0].id,
            MapCandidateStatus.VALIDATED,
            name="Injection — quantité/régime",
        )

    logger.info("Seeded demo data (vehicle #%d).", golf.id)
    return True
