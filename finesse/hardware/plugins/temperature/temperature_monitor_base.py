"""Provides a base class for temperature monitor devices or mock devices."""
from abc import abstractmethod
from decimal import Decimal

from finesse.config import TEMPERATURE_MONITOR_TOPIC
from finesse.hardware.device import DeviceBaseType


class TemperatureMonitorBase(
    DeviceBaseType,
    name=TEMPERATURE_MONITOR_TOPIC,
    description="Temperature monitor",
):
    """The base class for temperature monitor devices or mock devices."""

    @abstractmethod
    def get_temperatures(self) -> list[Decimal]:
        """Get the current temperatures."""
