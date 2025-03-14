"""Tests for the DataFileWriter class."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

import pytest
import yaml

from frog.config import TEMPERATURE_MONITOR_TOPIC
from frog.hardware.data_file_writer import (
    DataFileWriter,
    _get_metadata,
    _on_error_occurred,
)


@pytest.fixture
def writer() -> DataFileWriter:
    """A fixture providing a DataFileWriter."""
    return DataFileWriter()


def test_init(subscribe_mock: MagicMock) -> None:
    """Test DataFileWriter's constructor."""
    writer = DataFileWriter()
    subscribe_mock.assert_has_calls(
        (call(writer.open, "data_file.open"), call(writer.close, "data_file.close"))
    )


@patch("frog.hardware.data_file_writer.config.NUM_TEMPERATURE_MONITOR_CHANNELS", 2)
@patch("frog.hardware.data_file_writer._get_metadata")
@patch("frog.hardware.data_file_writer.Writer")
def test_open(
    csv_writer_mock: Mock,
    get_metadata_mock: Mock,
    writer: DataFileWriter,
    subscribe_mock: MagicMock,
    sendmsg_mock: MagicMock,
) -> None:
    """Test the open() method."""
    header = MagicMock()
    get_metadata_mock.return_value = header
    csv_writer = MagicMock()
    csv_writer_mock.return_value = csv_writer
    path = Path("/my/path.csv")
    writer.open(path)
    csv_writer_mock.assert_called_once_with(path, header, line_buffering=True)
    assert writer._writer is csv_writer
    csv_writer.writerow.assert_called_once_with(
        (
            "Date",
            "Time",
            "Temp1",
            "Temp2",
            "TimeAsSeconds",
            "Angle",
            "IsMoving",
            "TemperatureControllerPower",
        )
    )
    subscribe_mock.assert_has_calls(
        (
            call(writer.write, f"device.{TEMPERATURE_MONITOR_TOPIC}.data.response"),
            call(_on_error_occurred, "data_file.error"),
        )
    )
    sendmsg_mock.assert_called_once_with("data_file.opened")


@patch("frog.hardware.data_file_writer.Writer")
def test_open_error(
    csv_writer_mock: Mock,
    writer: DataFileWriter,
    sendmsg_mock: MagicMock,
    subscribe_mock: MagicMock,
) -> None:
    """Test the open() method handles errors correctly."""
    error = Exception()
    csv_writer_mock.side_effect = error
    writer.open(Path("/my/path.csv"))

    subscribe_mock.assert_not_called()
    sendmsg_mock.assert_called_once_with("data_file.error", error=error)


@patch("frog.hardware.data_file_writer.os.fsync")
def test_close(
    fsync_mock: Mock, writer: DataFileWriter, unsubscribe_mock: MagicMock
) -> None:
    """Test the close() method."""
    writer._writer = csv_writer = MagicMock()
    csv_writer._file.fileno.return_value = 42
    writer.close()
    assert not hasattr(writer, "_writer")  # Should have been deleted

    fsync_mock.assert_called_once_with(42)
    csv_writer.close.assert_called_once_with()
    unsubscribe_mock.assert_has_calls(
        (
            call(writer.write, f"device.{TEMPERATURE_MONITOR_TOPIC}.data.response"),
            call(_on_error_occurred, "data_file.error"),
        )
    )


def test_get_metadata() -> None:
    """Test _get_metadata().

    Checks that the result is convertible to YAML and that the number of lines output
    hasn't changed as users may be relying on this for parsing.
    """
    metadata = _get_metadata("FILENAME")
    serialised = str(yaml.safe_dump(metadata))
    assert serialised.count("\n") == 12


@patch("frog.hardware.data_file_writer.get_temperature_controller_instance")
@patch("frog.hardware.data_file_writer.get_stepper_motor_instance")
def test_write(
    get_stepper_mock: Mock,
    get_tc_mock: Mock,
    writer: DataFileWriter,
    sendmsg_mock: Mock,
) -> None:
    """Test the write() method."""
    get_stepper_mock.return_value = stepper = MagicMock()
    stepper.angle = 90.0
    stepper.is_moving = False
    get_tc_mock.return_value = hot_bb = MagicMock()
    hot_bb.power = 10

    time = datetime(2023, 4, 14, 0, 1, 0)  # one minute past midnight
    data = [Decimal(i) for i in range(3)]

    writer._writer = MagicMock()
    writer.write(time, data)
    writer._writer.writerow.assert_called_once_with(
        ("20230414", "00:01:00", *data, 60, 90.0, False, 10)
    )

    sendmsg_mock.assert_called_once_with("data_file.writing")


@patch("frog.hardware.data_file_writer.get_temperature_controller_instance")
@patch("frog.hardware.data_file_writer.get_stepper_motor_instance")
def test_write_moving(
    get_stepper_mock: Mock,
    get_tc_mock: Mock,
    writer: DataFileWriter,
    sendmsg_mock: Mock,
) -> None:
    """Test the write() method when the stepper motor is moving."""
    get_stepper_mock.return_value = stepper = MagicMock()
    stepper.angle = 95.0
    stepper.is_moving = True
    get_tc_mock.return_value = hot_bb = MagicMock()
    hot_bb.power = 10

    time = datetime(2023, 4, 14, 0, 1, 0)  # one minute past midnight
    data = [Decimal(i) for i in range(3)]

    writer._writer = MagicMock()
    writer.write(time, data)
    writer._writer.writerow.assert_called_once_with(
        ("20230414", "00:01:00", *data, 60, 95.0, True, 10)
    )

    sendmsg_mock.assert_called_once_with("data_file.writing")


@patch("frog.hardware.data_file_writer.get_temperature_controller_instance")
@patch("frog.hardware.data_file_writer.get_stepper_motor_instance")
def test_write_error(
    get_stepper_mock: Mock,
    get_tc_mock: Mock,
    writer: DataFileWriter,
    sendmsg_mock: MagicMock,
) -> None:
    """Test the write() method when an error occurs."""
    get_stepper_mock.return_value = stepper = MagicMock()
    stepper.angle = 90.0
    stepper.angle = False
    get_tc_mock.return_value = hot_bb = MagicMock()
    hot_bb.power = 10

    time = datetime(2023, 4, 14, 0, 1, 0)  # one minute past midnight
    data = [Decimal(i) for i in range(3)]

    writer._writer = MagicMock()
    error = Exception()
    writer._writer.writerow.side_effect = error
    writer.write(time, data)
    sendmsg_mock.assert_called_once_with("data_file.error", error=error)
