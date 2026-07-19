"""UI smoke tests (offscreen). Verify the main window builds, reacts to
domain events and renders models without a display server."""

from __future__ import annotations

import pytest

pyside = pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from calforge.services.dto import VehicleInput  # noqa: E402
from calforge.ui.main_window import MainWindow  # noqa: E402
from calforge.ui.models import HexTableModel  # noqa: E402
from calforge.ui.theme import apply_dark_theme  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    apply_dark_theme(app)
    return app


def test_main_window_lists_created_vehicle(qapp, context) -> None:
    window = MainWindow(context)
    try:
        assert window._vehicle_model.rowCount() == 0
        context.vehicles.create(VehicleInput(make="BMW", model="M2", year=2021))
        qapp.processEvents()
        assert window._vehicle_model.rowCount() == 1
        assert window._vehicle_model.vehicle_at(0).display_name == "BMW M2 2021"
    finally:
        window.close()


def test_search_filters_list(qapp, context) -> None:
    context.vehicles.create(VehicleInput(make="BMW", model="M2"))
    context.vehicles.create(VehicleInput(make="Audi", model="RS3"))
    window = MainWindow(context)
    try:
        window._search.setText("audi")
        qapp.processEvents()
        assert window._vehicle_model.rowCount() == 1
        assert window._vehicle_model.vehicle_at(0).make == "Audi"
    finally:
        window.close()


def test_vehicle_folder_panel_populates(qapp, context, sample_bin, tmp_path) -> None:
    from datetime import UTC, datetime

    from calforge.data.models import AttachmentCategory, HistoryEntryType
    from calforge.services.dto import HistoryEntryInput, ProjectInput

    vehicle = context.vehicles.create(VehicleInput(make="Audi", model="RS3", year=2022))
    context.projects.create(ProjectInput(vehicle_id=vehicle.id, name="Stage 1"))
    context.history.add(
        HistoryEntryInput(
            vehicle_id=vehicle.id,
            entry_type=HistoryEntryType.INTERVENTION,
            title="Pose décata",
            occurred_at=datetime.now(UTC),
        )
    )
    doc = tmp_path / "facture.pdf"
    doc.write_bytes(b"%PDF fake")
    context.attachments.add(vehicle.id, doc, category=AttachmentCategory.INVOICE)
    context.ecu_files.import_file(sample_bin, vehicle_id=vehicle.id)

    window = MainWindow(context)
    try:
        window._vehicle_list.setCurrentIndex(window._vehicle_model.index(0))
        qapp.processEvents()
        panel = window._details
        assert panel._project_model.rowCount() == 1
        assert panel._history_model.rowCount() == 1
        assert panel._attachment_model.rowCount() == 1
        assert panel._file_model.rowCount() == 1
    finally:
        window.close()


def test_library_search_filters(qapp, context, sample_bin, tmp_path) -> None:
    golf = context.vehicles.create(VehicleInput(make="VW", model="Golf"))
    context.ecu_files.import_file(sample_bin, vehicle_id=golf.id)
    other = tmp_path / "autre.bin"
    other.write_bytes(b"other-content")
    context.ecu_files.import_file(other, vehicle_id=golf.id)

    window = MainWindow(context)
    try:
        library = window._library
        assert library._model.rowCount() == 2
        library._search.setText("autre")
        qapp.processEvents()
        assert library._model.rowCount() == 1
        assert library._model.item_at(0).original_filename == "autre.bin"
    finally:
        window.close()


def test_worker_result_reaches_gui_thread(qapp) -> None:
    """Regression: QRunnable auto-deletion used to destroy the signals object
    before the queued emission was delivered, silently dropping results."""
    import threading
    import time

    from calforge.ui.workers import run_in_background

    main_thread = threading.get_ident()
    outcome: list[tuple] = []

    run_in_background(
        lambda: 42,
        on_done=lambda value: outcome.append((value, threading.get_ident() == main_thread)),
        on_error=lambda message: outcome.append(("error", message)),
    )

    deadline = time.monotonic() + 5
    while not outcome and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)

    assert outcome == [(42, True)]


def test_ecu_file_view_and_compare_view(qapp, context, tmp_path) -> None:
    """The per-file analysis view and the side-by-side compare view build,
    load content asynchronously and populate their models."""
    import time

    from tests.test_mapdetect import build_synthetic_dump

    from calforge.ui.views.ecu_file_view import EcuFileView
    from calforge.ui.views.hex_compare import HexCompareView

    data, _offset = build_synthetic_dump()
    path_a = tmp_path / "a.bin"
    path_a.write_bytes(data)
    modified = bytearray(data)
    modified[0x40] ^= 0xFF
    path_b = tmp_path / "b.bin"
    path_b.write_bytes(bytes(modified))

    vehicle = context.vehicles.create(VehicleInput(make="VW", model="Polo"))
    file_a = context.ecu_files.import_file(path_a, vehicle_id=vehicle.id)
    file_b = context.ecu_files.import_file(path_b, vehicle_id=vehicle.id)

    file_view = EcuFileView(context, file_a)
    compare_view = HexCompareView(context, file_a, file_b)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and (
        file_view._hex_model.rowCount() == 0 or compare_view._region_model.rowCount() == 0
    ):
        qapp.processEvents()
        time.sleep(0.01)

    assert file_view._hex_model.rowCount() > 0
    assert compare_view._region_model.rowCount() == 1
    region = compare_view._region_model.item_at(0)
    assert region.offset == 0x40


def test_hex_model_highlights() -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor

    model = HexTableModel()
    model.set_data(bytes(64))
    color = QColor("#ff0000")
    model.set_highlights([(0x10, 0x14, color)])

    highlighted = model.data(model.index(1, 0), Qt.ItemDataRole.BackgroundRole)
    outside = model.data(model.index(0, 0), Qt.ItemDataRole.BackgroundRole)
    assert highlighted == color
    assert outside is None
    assert model.index_for_offset(0x13).row() == 1
    assert model.index_for_offset(0x13).column() == 3


def test_hex_model_renders_rows() -> None:
    model = HexTableModel()
    model.set_data(bytes(range(40)))
    assert model.rowCount() == 3  # 40 bytes / 16 per row
    assert model.data(model.index(0, 0)) == "00"
    assert model.data(model.index(1, 0)) == "10"
    ascii_column = model.columnCount() - 1
    assert "·" in model.data(model.index(0, ascii_column))
