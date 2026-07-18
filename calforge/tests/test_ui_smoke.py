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


def test_hex_model_renders_rows() -> None:
    model = HexTableModel()
    model.set_data(bytes(range(40)))
    assert model.rowCount() == 3  # 40 bytes / 16 per row
    assert model.data(model.index(0, 0)) == "00"
    assert model.data(model.index(1, 0)) == "10"
    ascii_column = model.columnCount() - 1
    assert "·" in model.data(model.index(0, ascii_column))
