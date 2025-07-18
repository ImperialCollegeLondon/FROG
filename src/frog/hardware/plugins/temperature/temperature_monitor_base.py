"""Provides a base class for temperature monitor devices or mock devices."""

from abc import abstractmethod
from collections.abc import Sequence

from frog.config import TEMPERATURE_MONITOR_TOPIC
from frog.hardware.device import Device


class TemperatureMonitorBase(
    Device,
    name=TEMPERATURE_MONITOR_TOPIC,
    description="Temperature monitor",
):
    """The base class for temperature monitor devices or mock devices."""

    @abstractmethod
    def get_temperatures(self) -> Sequence:
        """Get the current temperatures."""
