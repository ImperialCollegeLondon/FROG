"""Provides a base class for interfacing with the OPUS program."""

from __future__ import annotations

from abc import abstractmethod

from frog.hardware.plugins.spectrometer.spectrometer_base import SpectrometerBase


class OPUSError(Exception):
    """Indicates that an error occurred with an OPUS device."""

    @classmethod
    def from_response(cls, errcode: int, errtext: str) -> OPUSError:
        """Create an OPUSError from the information given in the device response."""
        return cls(f"Error {errcode}: {errtext}")


class OPUSInterfaceBase(SpectrometerBase):
    """Base class providing an interface to the OPUS program."""

    def connect(self) -> None:
        """Connect to the spectrometer."""
        self.request_command("connect")

    def start_measuring(self) -> None:
        """Start a new measurement."""
        self.request_command("start")

    def stop_measuring(self) -> None:
        """Stop the current measurement."""
        self.request_command("cancel")

    @abstractmethod
    def request_command(self, command: str) -> None:
        """Request that OPUS run the specified command.

        Args:
            command: Name of command to run
        """
