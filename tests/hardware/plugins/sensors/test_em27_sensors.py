"""Tests for the EM27Sensors class."""

from decimal import Decimal
from importlib import resources
from unittest.mock import MagicMock, Mock, patch

import pytest

from frog.config import EM27_SENSORS_URL
from frog.hardware.plugins.sensors.em27_sensors import (
    EM27Error,
    EM27Sensors,
    SensorReading,
    get_em27_sensor_data,
)


@pytest.fixture
def sensor_reading():
    """Fixture for SensorReading."""
    return SensorReading("Voltage", Decimal("1.23"), "V")


def test_str(sensor_reading: SensorReading):
    """Test SensorReading's __str__() method."""
    assert str(sensor_reading) == "Voltage = 1.230000 V"


def test_val_str(sensor_reading: SensorReading):
    """Test SensorReading's val_str() method."""
    assert sensor_reading.val_str() == "1.230000 V"


@pytest.fixture
def em27_sensors(qtbot, subscribe_mock) -> EM27Sensors:
    """Fixture for EM27Sensors."""
    return EM27Sensors()


def test_init() -> None:
    """Test EM27Sensors's constructor."""
    sensors = EM27Sensors("1.2.3.4", 2.0)
    assert sensors._url == EM27_SENSORS_URL.format(host="1.2.3.4")


@patch("frog.hardware.plugins.sensors.em27_sensors.get_em27_sensor_data")
def test_handle_response(
    get_em27_sensor_data_mock: Mock, em27_sensors: EM27Sensors, qtbot
) -> None:
    """Test the _on_reply_received() method works when no error occurs."""
    # NB: This value is of the wrong type, but it doesn't matter here
    get_em27_sensor_data_mock.return_value = "sensor readings"

    with patch.object(em27_sensors, "send_readings_message") as send_mock:
        em27_sensors.handle_response(MagicMock())
        send_mock.assert_called_once_with("sensor readings")


@patch("frog.hardware.plugins.sensors.em27_sensors.get_em27_sensor_data")
def test_handle_response_exception(
    get_em27_sensor_data_mock: Mock, em27_sensors: EM27Sensors, qtbot
) -> None:
    """Test the handle_response() method works when an exception is raised."""
    # Make get_em27_sensor_data() raise an exception
    error = Exception()
    get_em27_sensor_data_mock.side_effect = error

    with pytest.raises(Exception):
        em27_sensors.handle_response(MagicMock())


def test_get_em27_sensor_data() -> None:
    """Test the get_em27_sensor_data() function.

    Read in the snapshot of the EM27 webpage and ensure that
    the sensor data is correctly extracted from it.
    """
    dummy_em27_fp = resources.files("frog.hardware.plugins.sensors").joinpath(
        "diag_autom.htm"
    )
    with dummy_em27_fp.open() as f:
        content = f.read()
    data_table = get_em27_sensor_data(content)
    assert len(data_table) == 7
    for entry in data_table:
        assert isinstance(entry, SensorReading)


def test_get_em27_sensor_data_no_table_found() -> None:
    """Test the get_em27_sensor_data() function.

    Read in HTML content which does not contain a valid sensor data table
    to verify that an exception is raised.
    """
    content = "<HTML>No EM27 sensor data here</HTML>\n"
    with pytest.raises(EM27Error):
        get_em27_sensor_data(content)
