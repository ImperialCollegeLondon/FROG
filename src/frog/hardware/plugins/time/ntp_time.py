"""This module provides an interface for querying time from an NTP server."""

import logging

from ntplib import NTPClient
from PySide6.QtCore import QTimer

from frog.config import (
    TIME_NTP_HOST,
    TIME_NTP_POLL_INTERVAL,
    TIME_NTP_PORT,
    TIME_NTP_TIMEOUT,
    TIME_NTP_VERSION,
)
from frog.hardware.plugins.time.time_base import TimeBase


class NTPTimeError(Exception):
    """Indicates that an error occurred while querying the NTP time server."""


class NTPTime(
    TimeBase,
    description="NTP time",
    parameters={
        "ntp_host": "The NTP server to query",
        "ntp_version": "The NTP version to use",
        "ntp_port": "The port to connect to",
        "ntp_timeout": "The maximum time to wait for a response",
        "ntp_poll_interval": "How often to query the NTP server (seconds)",
    },
):
    """A time source that queries an NTP server."""

    def __init__(
        self,
        ntp_host: str = TIME_NTP_HOST,
        ntp_version: int = TIME_NTP_VERSION,
        ntp_port: int = TIME_NTP_PORT,
        ntp_timeout: float = TIME_NTP_TIMEOUT,
        ntp_poll_interval: float = TIME_NTP_POLL_INTERVAL,
    ) -> None:
        """Create a new NTPTime.

        Args:
            ntp_host: The IP address or hostname of the NTP server
            ntp_version: The NTP version to use
            ntp_port: The port to connect to
            ntp_timeout: The maximum time to wait for a response
            ntp_poll_interval: How often to query the NTP server (seconds)
        """
        super().__init__()
        self._client = NTPClient()
        self._ntp_host = ntp_host
        self._ntp_version = ntp_version
        self._ntp_port = ntp_port
        self._ntp_timeout = ntp_timeout

        # Set up time offset polling.
        self.poll_time_offset()
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self.poll_time_offset)
        self._poll_timer.start(int(ntp_poll_interval * 1000))

    def poll_time_offset(self) -> None:
        """Query the NTP server for the current time offset."""
        logging.info("Polling NTP server for time offset.")
        try:
            self._response = self._client.request(
                self._ntp_host,
                version=self._ntp_version,
                port=self._ntp_port,
                timeout=self._ntp_timeout,
            )
            logging.info(f"NTP time offset: {self._response.offset}")
        except Exception as e:
            raise NTPTimeError(f"Error querying NTP server: {e}")

    def get_time_offset(self) -> float:
        """Get the current time offset in seconds.

        Returns:
            A float representing the current time offset.
        """
        return self._response.offset

    def close(self) -> None:
        """Close the device."""
        self._poll_timer.stop()
        super().close()
