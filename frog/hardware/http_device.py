"""Provides a device which communicates via HTTP requests."""

from abc import abstractmethod
from collections.abc import Callable
from functools import partial
from typing import Any

from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from frog.hardware.device import AbstractDevice


class HTTPDevice(
    AbstractDevice,
    parameters={
        "timeout": "The maximum time in seconds to wait for a response from the server"
    },
):
    """A device which communicates via HTTP requests."""

    def __init__(self, timeout: float) -> None:
        """Create a new HTTPDevice.

        Args:
            timeout: The maximum time in seconds to wait for a response from the server
        """
        self._timeout = timeout
        self._manager = QNetworkAccessManager()

    def make_request(
        self, url: str, callback: Callable[[str], Any] | None = None
    ) -> None:
        """Make a new HTTP request in the background.

        Args:
            url: The URL to connect to
            callback: A function to be called when a successful response is received
        """
        if not callback:
            callback = self.handle_response

        request = QNetworkRequest(url)
        request.setTransferTimeout(round(1000 * self._timeout))
        reply = self._manager.get(request)
        reply.finished.connect(
            partial(self.pubsub_errors(self._on_reply_received), reply, callback)
        )

    @abstractmethod
    def handle_response(self, response: str) -> None:
        """The default callback for successful HTTP responses."""

    def _on_reply_received(
        self, reply: QNetworkReply, callback: Callable[[str], Any]
    ) -> None:
        """Handle received HTTP reply."""
        if reply.error() != QNetworkReply.NetworkError.NoError:
            raise RuntimeError(f"Network error: {reply.errorString()}")

        # Parse the received message
        data: bytes = reply.readAll().data()
        callback(data.decode())
