"""Provides a base class for temperature monitor devices or mock devices."""

import re
from abc import abstractmethod
from collections.abc import Sequence

from frog.config import (
    NUM_TEMPERATURE_MONITOR_CHANNELS,
    TEMPERATURE_MONITOR_TOPIC,
)
from frog.hardware.device import Device


def _parse_channel_idx(input: str) -> int:
    """Get the temperature index from a string.

    >>> _parse_channel_idx("CH1")
    0

    Args:
        input: String input
    """
    if match := re.match(r"^CH([0-9]+)$", input):
        if num_str := match.group(1):
            num = int(num_str)
            if not (1 <= num <= NUM_TEMPERATURE_MONITOR_CHANNELS):
                raise ValueError(
                    "Channel number must be between 1 and "
                    f"{NUM_TEMPERATURE_MONITOR_CHANNELS} inclusive"
                )

            # Subtract one because we want the index starting at zero
            return num - 1

    raise ValueError(f"{input} is not a well-formed channel name")


_CHANNEL_NAMES = tuple(f"CH{i + 1}" for i in range(NUM_TEMPERATURE_MONITOR_CHANNELS))
"""Names for different temperature channels."""


class TemperatureMonitorBase(
    Device,
    name=TEMPERATURE_MONITOR_TOPIC,
    description="Temperature monitor",
    parameters={
        "hot_bb_channel": ("The channel for the hot black body", _CHANNEL_NAMES),
        "cold_bb_channel": ("The channel for the cold black body", _CHANNEL_NAMES),
    },
):
    """The base class for temperature monitor devices or mock devices."""

    def __init__(self, hot_bb_channel: str, cold_bb_channel: str) -> None:
        """Create a new TemperatureMonitorBase.

        Args:
            hot_bb_channel: Channel name for hot black body
            cold_bb_channel: Channel name for cold black body
        """
        super().__init__()

        hot_bb_idx = _parse_channel_idx(hot_bb_channel)
        cold_bb_idx = _parse_channel_idx(cold_bb_channel)
        if hot_bb_idx == cold_bb_idx:
            raise ValueError("Hot and cold black body channels cannot be the same")

        self._temperature_idx = {"hot_bb": hot_bb_idx, "cold_bb": cold_bb_idx}

    def signal_is_opened(self) -> None:
        """Signal that the device is now open.

        Send a message to frontend indicating what channels correspond to the hot and
        cold black bodies.
        """
        super().signal_is_opened()
        self.send_message("temperature_idx", temperature_idx=self._temperature_idx)

    @abstractmethod
    def get_temperatures(self) -> Sequence:
        """Get the current temperatures."""
