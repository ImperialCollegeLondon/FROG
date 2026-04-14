"""Tests for the interface to the DP9800 device."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from serial import SerialException

from frog.hardware.plugins.temperature.dp9800 import (
    DP9800,
    DP9800Error,
    calculate_bcc,
    check_data,
    parse_data,
)


@pytest.fixture
def data() -> bytes:
    """Example data.

    Data should look like:
    STX T t1 t2 t3 t4 t5 t6 t7 t8 t9 ff ETX BCC NUL
    """
    temperatures = [1.2, 3.4, 5.6, 7.8, 9.0, 2.3, 4.5, 6.7, 8.9]
    ff = "16"  # i.e. 0xx1x110  (TC, logging active, autoscan active, audible, deg C)
    bcc = "\x4f"
    data_string = (
        f"\x02\x54{temperatures[0]:8.2f}{temperatures[1]:8.2f}{temperatures[2]:8.2f}"
        f"{temperatures[3]:8.2f}{temperatures[4]:8.2f}{temperatures[5]:8.2f}"
        f"{temperatures[6]:8.2f}{temperatures[7]:8.2f}{temperatures[8]:8.2f}"
        f"{ff}\x03{bcc}\x00"
    )
    return bytes(data_string, "ascii")


@pytest.fixture
def dev(serial_mock: MagicMock) -> DP9800:
    """Get an instance of a DP9800 object."""
    return DP9800("CH7", "CH8", "COM1", 38400)


def test_check_data(data: bytes) -> None:
    """Test the check_data function."""
    # Remove STX and check for error
    data_string = "\x08" + data.decode("ascii")[1:]
    with pytest.raises(DP9800Error):
        check_data(bytes(data_string, "ascii"))

    # Remove ETX and check for error
    data_string = data.decode("ascii")[:-3] + "\x08" + data.decode("ascii")[-2:]
    with pytest.raises(DP9800Error):
        check_data(bytes(data_string, "ascii"))

    # Remove NUL and check for error
    data_string = data.decode("ascii")[:-1]
    with pytest.raises(DP9800Error):
        check_data(bytes(data_string, "ascii"))


def test_calculate_bcc(data: bytes) -> None:
    """Test the calculate_bcc function."""
    assert calculate_bcc(data) == data[-2]


def test_parse_data(data: bytes) -> None:
    """Test the parse_data function."""
    # Mangle BCC and check for error
    data_string = data.decode("ascii")[:-2] + "\x4e" + data.decode("ascii")[-1:]
    with pytest.raises(DP9800Error):
        parse_data(bytes(data_string, "ascii"))

    # Stick in a non-ASCII char and check for error
    data_string = data.decode("ascii")[:3] + "\x80" + data.decode("ascii")[4:]
    with pytest.raises(DP9800Error):
        parse_data(bytes(data_string, "utf-8"))

    temperatures_2_to_9, ff = parse_data(data)
    expected_temperatures = [
        Decimal(val) for val in [3.4, 5.6, 7.8, 9.0, 2.3, 4.5, 6.7, 8.9]
    ]
    expected_sysflag = "10110"  # from 0xx1x110
    assert temperatures_2_to_9 == pytest.approx(expected_temperatures)
    assert ff == expected_sysflag


def test_dp9800_get_device_settings(dev: DP9800) -> None:
    """Test DP9800's get_device_settings method."""
    # Use TC, logging active, autoscan active, audible, deg C
    settings = dev.get_device_settings("00010110")

    assert settings["instrument_type"] == "TC"
    assert settings["logging_state"] == "logging active"
    assert settings["scanning_state"] == "autoscan active"
    assert settings["audible_state"] == "audible"
    assert settings["temperature_unit"] == "deg C"

    # Use opposite settings, i.e.:
    # Use PT, logging inactive, autoscan inactive, silent, deg F
    settings = dev.get_device_settings("10000001")

    assert settings["instrument_type"] == "PT"
    assert settings["logging_state"] == "no logging"
    assert settings["scanning_state"] == "no scan"
    assert settings["audible_state"] == "silence"
    assert settings["temperature_unit"] == "deg F"


def test_dp9800_read_temperature_data(dev: DP9800, data: bytes) -> None:
    """Test DP9800's read_temperature_data method."""
    # Test successful read
    dev.serial.read_until.return_value = data
    dev.read_temperature_data()
    dev.serial.read_until.assert_called_once_with(b"\x00")

    # Test communication failure case
    dev.serial.read_until.side_effect = SerialException
    with pytest.raises(DP9800Error):
        dev.read_temperature_data()

    # Test insufficient data read case
    dev.serial.read_until.side_effect = None
    dev.serial.read_until.return_value = data[:3]
    with pytest.raises(DP9800Error):
        dev.read_temperature_data()


def test_dp9800_request_read(dev: DP9800) -> None:
    """Test DP9800's request_read method."""
    dev.request_read()
    dev.serial.write.assert_called_once_with(b"\x04T\x05")

    # Test communication failure case
    dev.serial.write.side_effect = Exception
    with pytest.raises(DP9800Error):
        dev.request_read()


@patch("frog.hardware.plugins.temperature.dp9800.DP9800.request_read")
@patch("frog.hardware.plugins.temperature.dp9800.DP9800.read_temperature_data")
def test_dp9800_get_temperatures(
    temperature_reader_mock: MagicMock, read_mock: MagicMock, dev: DP9800, data: bytes
) -> None:
    """Test DP9800's get_temperatures method."""
    temperature_reader_mock.return_value = data

    dev.get_temperatures()
    read_mock.assert_called_once()

    temperatures = dev.get_temperatures()
    expected = [Decimal(val) for val in [3.4, 5.6, 7.8, 9.0, 2.3, 4.5, 6.7, 8.9]]
    assert temperatures == pytest.approx(expected)
