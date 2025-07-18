"""This module contains interfaces for temperature-related hardware."""

from frog.hardware.manage_devices import get_device_instance
from frog.hardware.plugins.temperature.temperature_controller_base import (
    TemperatureControllerBase,
)
from frog.hardware.plugins.temperature.temperature_monitor_base import (
    TemperatureMonitorBase,
)


def get_temperature_controller_instance(name: str) -> TemperatureControllerBase | None:
    """Get the current temperature controller instance specified by name or None.

    Args:
        name: The name of the temperature controller instance (e.g. "hot_bb")
    """
    return get_device_instance(TemperatureControllerBase, name)


def get_temperature_monitor_instance() -> TemperatureMonitorBase | None:
    """Get the current temperature monitor device or None."""
    return get_device_instance(TemperatureMonitorBase)
