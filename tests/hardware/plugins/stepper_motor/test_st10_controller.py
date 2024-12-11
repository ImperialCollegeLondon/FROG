"""Tests for the ST10Controller class."""

from contextlib import nullcontext as does_not_raise
from itertools import chain
from typing import Any, cast
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from serial import SerialException, SerialTimeoutException

from frog.hardware.plugins.stepper_motor.st10_controller import (
    ST10AlarmCode,
    ST10Controller,
    ST10ControllerError,
    _SerialReader,
)

_SERIAL_ARGS = ("COM1", 9600)


class MockSerialReader(_SerialReader):
    """A mock version of _SerialReader that runs on the main thread."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Override the signals with MagicMocks."""
        self.async_read_completed = MagicMock()
        self.read_error = MagicMock()
        super().__init__(*args, **kwargs)

    def run(self) -> None:
        """Override the run method to make the thread do nothing."""

    def read_sync(self) -> str:
        """Read synchronously (mocked)."""
        self._process_read()
        return super().read_sync()


@pytest.fixture
@patch(
    "frog.hardware.plugins.stepper_motor.st10_controller._SerialReader",
    MockSerialReader,
)
def dev(subscribe_mock: MagicMock, serial_mock: MagicMock) -> ST10Controller:
    """A fixture providing an ST10Controller with a patched Serial object."""
    serial_mock.is_open = True

    # These functions should all be called, but patch them for now as we test this
    # elsewhere
    with patch.object(ST10Controller, "_check_device_id"):
        with patch.object(ST10Controller, "_home_and_reset"):
            with patch.object(ST10Controller, "signal_is_opened"):
                return ST10Controller(*_SERIAL_ARGS)


@patch(
    "frog.hardware.plugins.stepper_motor.st10_controller._SerialReader",
    MockSerialReader,
)
def test_init(subscribe_mock: MagicMock, serial_mock: MagicMock) -> None:
    """Test __init__()."""
    with patch.object(ST10Controller, "_check_device_id") as check_mock:
        with patch.object(ST10Controller, "_home_and_reset") as home_mock:
            # We assign to a variable so the destructor isn't invoked until after
            # our checks
            st10 = ST10Controller(*_SERIAL_ARGS)
            r = cast(MagicMock, st10._reader)
            r.async_read_completed.connect.assert_called_once_with(
                st10._on_initial_move_end
            )
            r.read_error.connect.assert_called_once_with(st10.send_error_message)
            check_mock.assert_called_once()
            home_mock.assert_called_once()


@patch("frog.hardware.plugins.stepper_motor.st10_controller.SerialDevice")
@patch("frog.hardware.plugins.stepper_motor.st10_controller.StepperMotorBase")
def test_close(stepper_cls: Mock, serial_dev_cls: Mock, dev: ST10Controller) -> None:
    """Test the close() method."""
    with patch.object(dev, "stop_moving") as stop_moving_mock:
        with patch.object(dev, "move_to") as move_mock:
            dev.close()
            stop_moving_mock.assert_called_once_with()
            move_mock.assert_called_once_with("nadir")

    # Check that both parents' close() methods are called
    stepper_cls.close.assert_called_once_with(dev)
    serial_dev_cls.close.assert_called_once_with(dev)


@patch("frog.hardware.plugins.stepper_motor.st10_controller.SerialDevice")
@patch("frog.hardware.plugins.stepper_motor.st10_controller.StepperMotorBase")
def test_close_move_fails(
    stepper_cls: Mock, serial_dev_cls: Mock, dev: ST10Controller
) -> None:
    """Test the close() method if the final move fails.

    We don't want to raise an exception in this case, just warn.
    """
    with patch.object(dev, "stop_moving"):
        with patch.object(dev, "move_to") as move_mock:
            move_mock.side_effect = SerialTimeoutException
            dev.close()

    # Check that both parents' close() methods are called
    stepper_cls.close.assert_called_once_with(dev)
    serial_dev_cls.close.assert_called_once_with(dev)


@patch("frog.hardware.plugins.stepper_motor.st10_controller.SerialDevice")
@patch("frog.hardware.plugins.stepper_motor.st10_controller.StepperMotorBase")
def test_close_already_closed(
    stepper_cls: Mock, serial_dev_cls: Mock, dev: ST10Controller
) -> None:
    """Test the close() method if the serial device is already closed."""
    dev.serial.is_open = False
    with patch.object(dev, "stop_moving") as stop_moving_mock:
        with patch.object(dev, "move_to") as move_mock:
            dev.close()
            stop_moving_mock.assert_not_called()
            move_mock.assert_not_called()


def test_on_initial_move_end(dev: ST10Controller) -> None:
    """Test the _on_initial_move_end() method."""
    with patch.object(dev, "_init_error_timer") as timer_mock:
        with patch.object(dev, "_reader") as reader_mock:
            with patch.object(dev, "signal_is_opened") as signal_mock:
                dev._on_initial_move_end()
                reader_mock.async_read_completed.disconnect.assert_called_once_with(
                    dev._on_initial_move_end
                )
                reader_mock.async_read_completed.connect.assert_called_once_with(
                    dev.send_move_end_message
                )
                timer_mock.stop.assert_called_once_with()
                signal_mock.assert_called_once_with()


@patch(
    "frog.hardware.plugins.stepper_motor.st10_controller.ST10Controller.angle",
    new_callable=PropertyMock,
)
def test_send_move_end_message(
    angle_mock: PropertyMock, sendmsg_mock: MagicMock, dev: ST10Controller
) -> None:
    """Test the send_move_end_message() method."""
    angle_mock.return_value = 12.34
    dev.send_move_end_message()
    sendmsg_mock.assert_called_once()


def read_mock(dev: ST10Controller, return_value: str):
    """Patch the _read_sync() method of dev."""
    return patch.object(dev, "_read_sync", return_value=return_value)


def test_write(dev: ST10Controller) -> None:
    """Test the _write() method."""
    dev._write("hello")
    dev.serial.write.assert_called_once_with(b"hello\r")


def test_read_normal(dev: ST10Controller) -> None:
    """Test the _read_sync() method with a valid message."""
    dev.serial.read_until.return_value = b"hello\r"
    ret = dev._read_sync()
    dev.serial.read_until.assert_called_with(b"\r")
    assert ret == "hello"


def test_read_error(dev: ST10Controller) -> None:
    """Test the _read_sync() method with an I/O error."""
    dev.serial.read_until.return_value = b"hello\r"
    dev.serial.read_until.side_effect = SerialException()

    with pytest.raises(SerialException):
        dev._read_sync()
        dev.serial.read_until.assert_called_with(b"\r")

    # Check that the error signal was triggered
    reader = cast(MagicMock, dev._reader.read_error)
    reader.emit.assert_called_once()


def test_read_timed_out(dev: ST10Controller) -> None:
    """Test the _read_sync() method with a timed-out response."""
    with patch.object(dev._reader, "out_queue") as queue_mock:
        queue_mock.get.side_effect = Exception
        with pytest.raises(SerialTimeoutException):
            dev._read_sync()


def test_read_non_ascii(dev: ST10Controller) -> None:
    """Test the _read_sync() method with a non-ASCII response."""
    dev.serial.read_until.return_value = b"\xff\r"
    with pytest.raises(ST10ControllerError):
        dev._read_sync()

    # Check that the error signal was triggered
    reader = cast(MagicMock, dev._reader.read_error)
    reader.emit.assert_called_once()


@pytest.mark.parametrize(
    "response,raises",
    [
        (
            response,
            does_not_raise()
            if response in ("%", "*")
            else pytest.raises(ST10ControllerError),
        )
        for response in ["%", "*", "?error", "something else"]
    ],
)
def test_check_response(response: str, raises: Any, dev: ST10Controller) -> None:
    """Test the _check_response() method."""
    with read_mock(dev, response):
        with raises:
            dev._check_response()


def test_write_check(dev: ST10Controller) -> None:
    """Test the _write_check() method."""
    with patch.object(dev, "_write") as write_mock:
        with patch.object(dev, "_check_response") as check_mock:
            dev._write_check("hello")
            write_mock.assert_called_once_with("hello")
            check_mock.assert_called_once()


@pytest.mark.parametrize(
    "name,value,response,raises",
    [
        (
            name,
            value,
            response,
            does_not_raise()
            if response.startswith(f"{name}=")
            else pytest.raises(ST10ControllerError),
        )
        for name in ["hello", "IS", "IP"]
        for value in ["", "value", "123"]
        for response in [f"{name}={value}", value, "%", "*", "?4"]
    ],
)
def test_request_value(
    name: str, value: str, response: str, raises: Any, dev: ST10Controller
) -> None:
    """Test the _request_value() method."""
    with patch.object(dev, "_write") as write_mock:
        with read_mock(dev, response):
            with raises:
                assert dev._request_value(name) == value
            write_mock.assert_called_once_with(name)


def test_check_device_id(dev: ST10Controller) -> None:
    """Test the _check_device_id() method."""
    # Check with the correct ID
    with read_mock(dev, "107F024"):
        dev._check_device_id()

    # Check with an invalid ID
    with read_mock(dev, "hello"):
        with pytest.raises(ST10ControllerError):
            dev._check_device_id()


_ALL_BITS = 0b101


@pytest.mark.parametrize(
    "all_bits,input,expected",
    ((_ALL_BITS, i, ((1 << (3 - i)) & _ALL_BITS != 0)) for i in range(1, 4)),
)
def test_get_input_status(
    dev: ST10Controller,
    all_bits: int,
    input: int,
    expected: bool,
) -> None:
    """Test the _get_input_status() method."""
    with patch.object(dev, "_request_value") as request_mock:
        request_mock.return_value = f"{all_bits:3b}"
        assert dev._get_input_status(input) == expected
        request_mock.assert_called_once_with("IS")


@pytest.mark.parametrize("input", (-1, 0, 4, 10))
def test_get_input_status_bad(dev: ST10Controller, input: int):
    """Test the _get_input_status() method fails for an out-of-range input."""
    with patch.object(dev, "_request_value") as request_mock:
        request_mock.return_value = f"{_ALL_BITS:3b}"
        with pytest.raises(ValueError):
            dev._get_input_status(input)


def test_steps_per_rotation(dev: ST10Controller) -> None:
    """Test the steps_per_rotation property."""
    assert dev.steps_per_rotation == 50800


@pytest.mark.parametrize("in_position", (True, False))
def test_home_and_reset(dev: ST10Controller, in_position: bool) -> None:
    """Test the _home_and_reset() method."""
    with patch.object(dev, "_send_string") as ss_mock:
        with patch.object(dev, "stop_moving") as stop_mock:
            with patch.object(dev, "_relative_move"):
                with patch.object(dev, "_write_check"):
                    with patch.object(dev, "_init_error_timer") as timer_mock:
                        with patch.object(dev, "_get_input_status") as status_mock:
                            # Let's not bother checking everything as we can't ensure
                            # the sequence is correct in any case
                            status_mock.return_value = in_position
                            dev._home_and_reset()
                            stop_mock.assert_called_once_with()
                            timer_mock.start.assert_called_once_with()
                            ss_mock.assert_called_once_with("Z")


@pytest.mark.parametrize("steps", range(0, 40, 7))
def test_relative_move(dev: ST10Controller, steps: int) -> None:
    """Test the _relative_move() method."""
    with patch.object(dev, "_write_check") as write_mock:
        dev._relative_move(steps)
        write_mock.assert_called_once_with(f"FL{steps}")


_STATUS_CODES = range(0, 0xFFFF, 272)
"""Some arbitrary status codes in the correct range."""


@pytest.mark.parametrize("status", _STATUS_CODES)
def test_status_code(dev: ST10Controller, status: int) -> None:
    """Test the status_code property."""
    with patch.object(dev, "_request_value") as request_mock:
        request_mock.return_value = f"{status:04x}"
        assert dev.status_code == status


@pytest.mark.parametrize("status", _STATUS_CODES)
@patch(
    "frog.hardware.plugins.stepper_motor.st10_controller.ST10Controller.status_code",
    new_callable=PropertyMock,
)
def test_is_moving(
    status_code_mock: PropertyMock, dev: ST10Controller, status: int
) -> None:
    """Test the is_moving property."""
    status_code_mock.return_value = status
    expected = status & 0x0010 != 0  # check moving bit is set
    assert dev.is_moving == expected


@pytest.mark.parametrize(
    "code,expected",
    (
        (0, None),
        (0x0004, ST10AlarmCode.CW_LIMIT),
        (0x0014, ST10AlarmCode.INTERNAL_VOLTAGE | ST10AlarmCode.CW_LIMIT),
    ),
)
def test_alarm_code(
    code: int,
    expected: ST10AlarmCode | None,
    dev: ST10Controller,
) -> None:
    """Test the alarm_code property."""
    with patch.object(dev, "_request_int") as request_mock:
        request_mock.return_value = code
        ret = dev.alarm_code
        request_mock.assert_called_once_with("AL", 16)
        assert ret == expected


@pytest.mark.parametrize(
    "step,response,raises",
    chain(
        [(step, f"IP={step}", does_not_raise()) for step in range(0, 250, 50)],
        [(4, "IP=hello", pytest.raises(ST10ControllerError))],
    ),
)
def test_get_step(
    step: int,
    response: str,
    raises: Any,
    dev: ST10Controller,
) -> None:
    """Test getting the step property."""
    with read_mock(dev, response):
        with raises:
            assert dev.step == step


@pytest.mark.parametrize("step", range(0, 40, 7))
def test_set_step(dev: ST10Controller, step: int) -> None:
    """Test setting the step property."""
    with patch.object(dev, "_write_check") as write_mock:
        with patch.object(dev, "_notify_on_stopped") as notify_mock:
            dev.step = step
            write_mock.assert_called_once_with(f"FP{step}")
            notify_mock.assert_called_once_with()


@pytest.mark.parametrize("string", ("a", "A", "Z", "hello"))
def test_send_string(dev: ST10Controller, string: str) -> None:
    """Test the _send_string() method."""
    with patch.object(dev, "_write_check") as write_mock:
        dev._send_string(string)
        write_mock.assert_called_once_with(f"SS{string}")


def test_stop_moving(dev: ST10Controller) -> None:
    """Test the stop_moving() method."""
    with patch.object(dev, "_write_check") as write_mock:
        dev.stop_moving()
        write_mock.assert_called_once_with("ST")
