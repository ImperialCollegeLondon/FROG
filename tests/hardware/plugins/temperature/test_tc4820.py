"""Tests for the interface to the TC4820 device."""

from contextlib import nullcontext as does_not_raise
from decimal import Decimal
from itertools import chain
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from pytest_mock import MockerFixture

from frog.hardware.device import RetryFailedError
from frog.hardware.plugins.temperature.tc4820 import TC4820, MalformedMessageError

_SERIAL_ARGS = ("COM1", 9600)


@pytest.fixture
def dev(serial_mock: MagicMock) -> TC4820:
    """Get an instance of a TC4820 object."""
    return TC4820("hot_bb", *_SERIAL_ARGS)


@pytest.mark.parametrize("name", ("hot_bb", "cold_bb"))
def test_init(name: str, subscribe_mock: MagicMock, serial_mock: MagicMock) -> None:
    """Test TC4820's constructor."""
    dev = TC4820(name, *_SERIAL_ARGS)
    assert dev.max_attempts == 3


def test_get_properties(dev: TC4820) -> None:
    """Test the get_properties() method."""
    expected = {
        "power": 0,
        "alarm_status": 0,
        "temperature": Decimal(0),
        "set_point": Decimal(0),
    }

    with patch.object(dev, "request_int") as mock_int:
        mock_int.return_value = 0
        assert dev.get_properties() == expected


def checksum(message: int) -> int:
    """Calculate the checksum as an int."""
    return sum(f"{message:0{4}x}".encode("ascii")) & 0xFF


def format_message(message: int, checksum: int, eol: str = "^") -> bytes:
    """Format the message as the device would."""
    assert 0 <= checksum <= 0xFF
    return f"*{message:0{4}x}{checksum:0{2}x}{eol}".encode("ascii")


_MESSAGE = "012345678"


def _get_message(len: int) -> tuple[int, bytes, Any]:
    substr = _MESSAGE[:len]
    value = int(substr, base=16)
    return (
        value,
        f"*{substr}{checksum(value):0{2}x}^".encode("ascii"),
        does_not_raise() if len == 4 else pytest.raises(MalformedMessageError),
    )


_TERM_CHARS = sorted(set("*^").intersection(map(chr, range(0, 128, 10))))
"""The correct start and end chars along with some other arbitrary ASCII chars."""


@pytest.mark.parametrize(
    "value,message,raises",
    chain(
        # This is a special message indicating that we provided a bad checksum to the
        # device
        [(0, b"*XXXX60^", pytest.raises(MalformedMessageError))],
        # Non-hex value for number
        [(0, b"*$$$$90^", pytest.raises(MalformedMessageError))],
        # Check that only valid start and end terminators work
        [
            (
                0,
                f"{start}0000c0{end}".encode("ascii"),
                does_not_raise()
                if start == "*" and end == "^"
                else pytest.raises(MalformedMessageError),
            )
            for end in _TERM_CHARS
            for start in _TERM_CHARS
        ],
        # Message length
        [_get_message(len) for len in range(1, len(_MESSAGE))],
        # Test checksums
        [
            (
                value,
                format_message(value, csum),
                does_not_raise()
                if checksum(value) == csum
                else pytest.raises(MalformedMessageError),
            )
            for value in (0x0000, 0x1234, 0x5678)
            for csum in range(0x100)
        ],
    ),
)
def test_read(value: int, message: bytes, raises: Any, dev: TC4820) -> None:
    """Test TC4820.read()."""
    with raises:
        with patch.object(dev.serial, "read_until", return_value=message) as mock:
            assert value == dev.read_int()
            mock.assert_called_once_with(b"^", size=8)


@pytest.mark.parametrize("value", range(0, 0xFFFF, 200))
def test_write(value: int, dev: TC4820) -> None:
    """Test TC4820.write()."""
    str_value = f"{value:0{4}x}"
    dev.send_command(str_value)
    dev.serial.write.assert_called_once_with(
        format_message(value, checksum(value), eol="\r")
    )


@pytest.mark.parametrize(
    "max_attempts,fail_max,raises",
    [
        (
            max_attempts,
            fail_max,
            pytest.raises(RetryFailedError)
            if fail_max >= max_attempts
            else does_not_raise(),
        )
        for fail_max in range(5)
        for max_attempts in range(1, 5)
    ],
)
def test_request_int(
    max_attempts: int, fail_max: int, raises: Any, dev: TC4820
) -> None:
    """Test TC4820.request_int().

    Check that the retrying of requests works.
    """
    dev.max_attempts = max_attempts

    fail_count = 0

    def my_read():
        """Raise an error the first fail_count times called."""
        nonlocal fail_count
        if fail_count < fail_max:
            fail_count += 1
            raise MalformedMessageError()

        return 0

    send_mock = MagicMock()
    with raises:
        with patch.object(dev, "send_command", send_mock):
            with patch.object(dev, "read_int", my_read):
                assert dev.request_int("some string") == 0
    send_mock.assert_called_with("some string")


@pytest.mark.parametrize(
    "name,command,type",
    [
        ("temperature", "010000", "decimal"),
        ("power", "020000", "int"),
        ("alarm_status", "030000", "int"),
        ("set_point", "500000", "decimal"),
    ],
)
def test_property_getters(
    name: str, command: str, type: str, dev: TC4820, mocker: MockerFixture
) -> None:
    """Check that the getters for properties work."""
    m = mocker.patch(f"frog.hardware.plugins.temperature.tc4820.TC4820.request_{type}")
    getattr(dev, name)
    m.assert_called_once_with(command)


@patch("frog.hardware.plugins.temperature.tc4820.SerialDevice")
@patch("frog.hardware.plugins.temperature.tc4820.TemperatureControllerBase")
def test_close(tc_base_cls: Mock, serial_dev_cls: Mock, dev: TC4820) -> None:
    """Test the close() method."""
    dev.close()
    tc_base_cls.close.assert_called_once_with(dev)
    serial_dev_cls.close.assert_called_once_with(dev)
