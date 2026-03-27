"""Tests for the Seneca Z-8AI device."""

from unittest.mock import MagicMock, patch

import numpy
import pytest

from frog.hardware.plugins.temperature.z8ai import Z8AI, Z8AIError

_SERIAL_ARGS = ("0403:6001 AB0LMVI5A", 57600)


@pytest.fixture
def dev(serial_mock: MagicMock) -> Z8AI:
    """Get an instance of a Seneca Z-8AI object."""
    return Z8AI(*_SERIAL_ARGS)


@pytest.fixture
def data() -> bytes:
    """Get raw test data."""
    return b"\x01\x03\x101d1p\xff\xfa\xff\xf81u\xff\xfa1d\xff\xfa]Z"


def test_init(serial_mock: MagicMock) -> None:
    """Test Seneca Z-8AI's constructor."""
    # Test default values
    dev = Z8AI(*_SERIAL_ARGS)
    assert dev.MIN_TEMP == -80
    assert dev.MAX_TEMP == 105
    assert dev.MIN_MILLIVOLT == 4
    assert dev.MAX_MILLIVOLT == 20

    # Test arg values
    dev = Z8AI(*_SERIAL_ARGS, 1, 2, 3, 4)
    assert dev.MIN_TEMP == 1
    assert dev.MAX_TEMP == 2
    assert dev.MIN_MILLIVOLT == 3
    assert dev.MAX_MILLIVOLT == 4


def test_write(dev: Z8AI) -> None:
    """Test Z8AI.write()."""
    dev.request_read()
    dev.serial.write.assert_called_once_with(bytearray([1, 3, 0, 2, 0, 8, 229, 204]))


def test_read(dev: Z8AI, data: bytes) -> None:
    """Test Z8AI.read()."""
    with patch.object(dev.serial, "read") as mock:
        mock.return_value = data
        assert data == dev.read()
        mock.assert_called_once()


@pytest.mark.parametrize(
    "message",
    (
        b"\x01\x03\x101d1p\xff\xfa\xff\xf81u\xff\xfa1d\xff",
        b"\x01\x03\x101d1p\xff\xfa\xff\xf81u\xff\xfa1d\xff\xfa]Z\x01\x03",
    ),
)
def test_read_length_error(dev: Z8AI, message: bytes) -> None:
    """Test Z8AI.read() error handling."""
    with pytest.raises(Z8AIError):
        with patch.object(dev.serial, "read", return_value=message):
            dev.read()


def test_parse_data(dev: Z8AI, data: bytes) -> None:
    """Test Z8AI.parse_data()."""
    expected = [
        19.946250000000006,
        20.085000000000008,
        numpy.nan,
        numpy.nan,
        20.14281249999999,
        numpy.nan,
        19.946250000000006,
        numpy.nan,
    ]
    parsed = dev.parse_data(data)

    numpy.testing.assert_allclose(parsed, expected)


def test_get_temperatures(dev: Z8AI, data: bytes) -> None:
    """Test Z8AI.get_temperatures()."""
    result = MagicMock()
    with patch.object(dev, "request_read") as request_mock:
        with patch.object(dev, "read", return_value=data) as read_mock:
            with patch.object(dev, "parse_data", return_value=result) as parse_mock:
                assert dev.get_temperatures() == result.tolist()

    request_mock.assert_called_once_with()
    read_mock.assert_called_once_with()
    parse_mock.assert_called_once_with(data)


def test_get_temperatures_retries_on_crc_error(dev: Z8AI, data: bytes) -> None:
    """Test that Z8AI.get_temperatures() retries when a CRC check fails."""
    result = MagicMock()
    with patch.object(dev, "request_read") as request_mock:
        with patch.object(dev, "read", return_value=data) as read_mock:
            with patch.object(
                dev,
                "parse_data",
                side_effect=[Z8AIError("CRC check failed"), result],
            ) as parse_mock:
                assert dev.get_temperatures() == result.tolist()

    assert request_mock.call_count == 2
    assert read_mock.call_count == 2
    assert parse_mock.call_count == 2
