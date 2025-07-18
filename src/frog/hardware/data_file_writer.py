"""Provides a class for writing sensor data to a CSV file."""

import logging
import os
import platform
from datetime import datetime
from decimal import Decimal
from math import floor
from pathlib import Path
from typing import Any

from csvy import Writer
from pubsub import pub

from frog import config
from frog.hardware.plugins.stepper_motor import get_stepper_motor_instance
from frog.hardware.plugins.temperature import get_temperature_controller_instance
from frog.hardware.pubsub_decorators import pubsub_errors


def _on_error_occurred(error: BaseException) -> None:
    """Close file in case of error."""
    pub.sendMessage("data_file.close")


def _get_platform_info() -> dict[str, str]:
    return {
        key: getattr(platform, key)() for key in ("platform", "python_version", "node")
    }


def _get_metadata(filename: str) -> dict[str, Any]:
    return {
        "encoding": "utf-8",
        "name": filename,
        "datetime": datetime.now().astimezone().isoformat(),  # include timezone
        "system": {
            "app": {
                "name": config.APP_NAME,
                "author": config.APP_AUTHOR,
                "version": config.APP_VERSION,
            },
            "platform": _get_platform_info(),
        },
    }


def _create_writer(path: Path) -> Writer:
    writer = Writer(path, _get_metadata(path.name), line_buffering=True)

    # Write column headers
    writer.writerow(
        (
            "Date",
            "Time",
            *(f"Temp{i + 1}" for i in range(config.NUM_TEMPERATURE_MONITOR_CHANNELS)),
            "TimeAsSeconds",
            "Angle",
            "IsMoving",
            "TemperatureControllerPower",
        )
    )

    return writer


def _get_stepper_motor_angle() -> tuple[float, bool]:
    """Get the current angle of the stepper motor.

    This function returns a float indicating the angle in degrees and a boolean
    indicating whether the motor is currently moving. If an error occurs, the angle
    returned will be nan.
    """
    stepper = get_stepper_motor_instance()

    # Stepper motor not connected
    if not stepper:
        return (float("nan"), False)

    try:
        angle = stepper.angle
        is_moving = stepper.is_moving
        return (angle, is_moving)
    except Exception as error:
        stepper.send_error_message(error)
        return (float("nan"), False)


def _get_hot_bb_power() -> float:
    """Get the current power of the hot BB temperature controller as a percentage.

    If an error occurs, nan will be returned.
    """
    hot_bb = get_temperature_controller_instance("hot_bb")

    # Hot BB temperature controller not connected
    if not hot_bb:
        return float("nan")

    try:
        return hot_bb.power
    except Exception as error:
        hot_bb.send_error_message(error)
        return float("nan")


class DataFileWriter:
    """A class for writing sensor data to a CSV file.

    This class is a singleton. Every time a new file needs to be written this instance
    is reused.
    """

    def __init__(self) -> None:
        """Create a new DataFileWriter."""
        self._writer: Writer
        """The CSV writer."""

        # Listen to open/close messages
        pub.subscribe(self.open, "data_file.open")
        pub.subscribe(self.close, "data_file.close")

        # Close data file if GUI closes unexpectedly
        pub.subscribe(self.close, "window.closed")

    @pubsub_errors("data_file.error")
    def open(self, path: Path) -> None:
        """Open a file at the specified path for writing.

        Args:
            path: The path of the file to write to
        """
        logging.info(f"Opening data file at {path}")
        self._writer = _create_writer(path)

        # Listen to temperature monitor messages
        pub.subscribe(
            self.write, f"device.{config.TEMPERATURE_MONITOR_TOPIC}.data.response"
        )

        # Call close() if writing errors occur
        pub.subscribe(_on_error_occurred, "data_file.error")

        # Send message to indicate that file has opened successfully
        pub.sendMessage("data_file.opened")

    def close(self) -> None:
        """Close the current file handle."""
        pub.unsubscribe(
            self.write, f"device.{config.TEMPERATURE_MONITOR_TOPIC}.data.response"
        )
        pub.unsubscribe(_on_error_occurred, "data_file.error")

        if hasattr(self, "_writer"):
            logging.info("Closing data file")

            # Ensure data is written to disk
            os.fsync(self._writer._file.fileno())

            self._writer.close()
            del self._writer

    @pubsub_errors("data_file.error")
    def write(self, time: datetime, temperatures: list[Decimal]) -> None:
        """Write temperature readings to the CSV file."""
        # Also include timestamp as seconds since midnight
        midnight = datetime(time.year, time.month, time.day)
        secs_since_midnight = floor((time - midnight).total_seconds())

        angle, is_moving = _get_stepper_motor_angle()
        self._writer.writerow(
            (
                time.strftime("%Y%m%d"),
                time.strftime("%H:%M:%S"),
                *(round(t, config.TEMPERATURE_PRECISION) for t in temperatures),
                secs_since_midnight,
                angle,
                int(is_moving),
                _get_hot_bb_power(),
            )
        )

        pub.sendMessage("data_file.writing")


_data_file_writer = DataFileWriter()
"""The only instance of DataFileWriter."""
