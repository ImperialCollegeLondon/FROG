"""Tests for the SensorsPanel."""

from unittest.mock import call, patch

from PySide6.QtWidgets import QLabel, QLineEdit

from frog.config import SENSORS_TOPIC
from frog.gui.sensors_panel import SensorsPanel
from frog.sensor_reading import SensorReading


@patch("frog.gui.sensors_panel.pub.subscribe")
def test_init(subscribe_mock, qtbot) -> None:
    """Test SensorsPanel's constructor."""
    panel = SensorsPanel()
    assert panel.title() == "Sensor readings"

    # Check the panel's widgets are created correctly
    assert not panel._poll_light._is_on

    # Check correct pubsub channels are subscribed to
    subscribe_mock.call_count == 2
    subscribe_mock.assert_has_calls(
        [
            call(panel._remove_readings_widgets, f"device.opened.{SENSORS_TOPIC}"),
            call(panel._on_readings_received, f"device.{SENSORS_TOPIC}.data"),
        ],
        any_order=True,
    )


def test_remove_readings_widgets() -> None:
    """Test the _remove_readings_widgets method."""
    panel = SensorsPanel()

    panel._get_reading_lineedit(SensorReading("Quantity1", 1.0, "quantity 1 units"))
    panel._get_reading_lineedit(SensorReading("Quantity2", -8.1, "quantity 2 units"))
    panel._get_reading_lineedit(SensorReading("Quantity3", 700, "quantity 3 units"))
    assert panel._reading_layout.rowCount() == 3

    panel._remove_readings_widgets()
    assert panel._reading_layout.rowCount() == 0


def test_get_reading_lineedit() -> None:
    """Test the _get_reading_lineedit method."""
    panel = SensorsPanel()

    assert panel._val_lineedits == {}

    reading = panel._get_reading_lineedit(
        SensorReading("Quantity1", 1.0, "quantity 1 units")
    )
    assert isinstance(reading, QLineEdit)
    assert panel._reading_layout.rowCount() == 1
    reading_name_label = panel._reading_layout.itemAt(0).widget()  # type: ignore[union-attr]
    assert isinstance(reading_name_label, QLabel)
    assert reading_name_label.text() == "Quantity1"


def test_on_readings_received() -> None:
    """Test the _on_readings_received method."""
    panel = SensorsPanel()

    readings = (
        SensorReading("Quantity1", 1.0, "quantity 1 units"),
        SensorReading("Quantity2", -8.1, "quantity 2 units"),
    )

    # Check LED flashes
    with patch.object(panel, "_poll_light") as poll_light_mock:
        panel._on_readings_received(readings)
        poll_light_mock.flash.assert_called_once()

    # Check lineedits are updated with correct text
    assert panel._reading_layout.rowCount() == 2
    assert panel._val_lineedits["Quantity1"].text() == f"{1.0:.6f} quantity 1 units"
    assert panel._val_lineedits["Quantity2"].text() == f"{-8.1:.6f} quantity 2 units"
