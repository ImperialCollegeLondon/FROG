"""Provides a base class for interfacing with the FTSW500 program."""

from __future__ import annotations

from abc import abstractmethod

from frog.hardware.plugins.spectrometer.spectrometer_base import SpectrometerBase


class FTSW500Error(Exception):
    """Indicates that an error occurred with an FTSW500 device."""


class FTSW500InterfaceBase(SpectrometerBase):
    """Base class providing an interface to the FTSW500 program."""

    def connect(self) -> None:
        """Connect to the spectrometer."""
        self.request_command("clickConnectButton")

    def start_measuring(self) -> None:
        """Start a new measurement."""
        self.request_command("clickStartAcquisitionButton")

    def stop_measuring(self) -> None:
        """Stop the current measurement."""
        self.request_command("clickStopAcquisitionButton")

    @abstractmethod
    def request_command(self, command: str) -> None:
        """Request that FTSW500 run the specified command.

        Args:
            command: Name of command to run
        """
