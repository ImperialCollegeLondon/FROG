"""Provides a generic base class for spectrometers."""

from abc import abstractmethod

from frog.config import SPECTROMETER_TOPIC
from frog.hardware.device import Device
from frog.spectrometer_status import SpectrometerStatus


class SpectrometerBase(Device, name=SPECTROMETER_TOPIC, description="Spectrometer"):
    """A generic base class for spectrometers."""

    def __init__(self) -> None:
        """Create a new SpectrometerBase."""
        super().__init__()

        for command in (
            "connect",
            "start_measuring",
            "stop_measuring",
        ):
            self.subscribe(getattr(self, command), command)

    @abstractmethod
    def connect(self) -> None:
        """Connect to the spectrometer."""

    @abstractmethod
    def start_measuring(self) -> None:
        """Start a new measurement."""

    @abstractmethod
    def stop_measuring(self) -> None:
        """Stop the current measurement."""

    def send_status_message(self, status: SpectrometerStatus) -> None:
        """Send a status update via pubsub."""
        self.send_message(f"status.{status.name.lower()}", status=status)
