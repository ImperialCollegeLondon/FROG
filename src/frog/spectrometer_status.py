"""Provides an enum representing the spectrometer's state."""

from enum import Enum


class SpectrometerStatus(Enum):
    """The state of the spectrometer.

    These values correspond to the status codes in the EM27 manual, but are used for all
    spectrometer types.
    """

    IDLE = 0
    CONNECTING = 1
    CONNECTED = 2
    MEASURING = 3
    FINISHING = 4
    CANCELLING = 5
    UNDEFINED = 6

    @property
    def is_connected(self) -> bool:
        """Whether the state represents a connected status."""
        return 2 <= self.value <= 5
