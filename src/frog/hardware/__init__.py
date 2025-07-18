"""This module contains code for interfacing with different hardware devices."""

from collections.abc import Sequence
from decimal import Decimal

from pubsub import pub

from frog.config import NUM_TEMPERATURE_MONITOR_CHANNELS, TEMPERATURE_MONITOR_TOPIC
from frog.hardware import data_file_writer  # noqa: F401
from frog.hardware.plugins.temperature import get_temperature_monitor_instance
from frog.hardware.plugins.time import get_current_time


def _try_get_temperatures() -> Sequence | None:
    """Try to read the current temperatures from the temperature monitor.

    If the device is not connected or the operation fails, None is returned.
    """
    dev = get_temperature_monitor_instance()
    if not dev:
        return None

    try:
        return dev.get_temperatures()
    except Exception as error:
        dev.send_error_message(error)
        return None


_DEFAULT_TEMPS = [Decimal("nan")] * NUM_TEMPERATURE_MONITOR_CHANNELS


def _send_temperatures() -> None:
    """Send the current temperatures (or NaNs) via pubsub."""
    temperatures = _try_get_temperatures()
    if temperatures is None:
        temperatures = _DEFAULT_TEMPS

    # Get time from the time source.
    time = get_current_time()

    pub.sendMessage(
        f"device.{TEMPERATURE_MONITOR_TOPIC}.data.response",
        temperatures=temperatures,
        time=time,
    )


pub.subscribe(_send_temperatures, f"device.{TEMPERATURE_MONITOR_TOPIC}.data.request")
