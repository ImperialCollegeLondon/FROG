"""This module contains interfaces for querying time sources."""

from datetime import datetime, timedelta

from frog.hardware.manage_devices import get_device_instance
from frog.hardware.plugins.time.time_base import TimeBase


def get_time_instance() -> TimeBase | None:
    """Get the instance of the current time source if connected or None."""
    return get_device_instance(TimeBase)


def get_current_time() -> datetime:
    """Read the current time, with optional time offset.

    If the time device is not connected or the operation fails, local time is returned.
    """
    time = datetime.now()
    if dev := get_time_instance():
        time += timedelta(seconds=dev.get_time_offset())

    return time
