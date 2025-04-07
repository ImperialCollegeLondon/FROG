"""Provides a device which communicates via HTTP requests."""

import logging
from abc import abstractmethod
from collections.abc import Callable
from functools import partial
from typing import Any

from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from frog.hardware.device import AbstractDevice


class HTTPDevice(
    AbstractDevice,
    parameters={
        "timeout": "The maximum time in seconds to wait for a response from the server",
        "default_retries": "The default number of times to retry a request if it fails",
    },
):
    """A device which communicates via HTTP requests."""

    def __init__(self, timeout: float, default_retries: int = 0) -> None:
        """Create a new HTTPDevice.

        Args:
            timeout: The maximum time in seconds to wait for a response from the server
            default_retries: The default number of times to retry a failed request
        """
        if timeout <= 0:
            raise ValueError("Timeout must be greater than zero")
        if default_retries < 0:
            raise ValueError("Retries must be greater than or equal to zero")

        self._timeout = timeout
        self._retries = default_retries
        self._manager = QNetworkAccessManager()

    def make_request(
        self,
        url: str,
        callback: Callable[[str], Any] | None = None,
        retries: int | None = None,
    ) -> None:
        """Make a new HTTP request in the background.

        Args:
            url: The URL to connect to
            callback: A function to be called when a successful response is received
            retries: Number of times to retry the request
        """
        if retries is None:
            retries = self._retries
        elif retries < 0:
            raise ValueError("Retries must be greater than or equal to zero")
        if not callback:
            callback = self.handle_response

        request = QNetworkRequest(url)
        request.setTransferTimeout(round(1000 * self._timeout))
        reply = self._manager.get(request)
        reply.finished.connect(
            partial(
                self.pubsub_errors(self._on_reply_received),
                reply,
                url,
                callback,
                retries,
            )
        )

    @abstractmethod
    def handle_response(self, response: str) -> None:
        """The default callback for successful HTTP responses."""

    def _on_reply_received(
        self,
        reply: QNetworkReply,
        url: str,
        callback: Callable[[str], Any],
        retries_remaining: int,
    ) -> None:
        """Handle received HTTP reply."""
        if reply.error() != QNetworkReply.NetworkError.NoError:
            if retries_remaining == 0:
                raise RuntimeError(f"Network error: {reply.errorString()}")

            # ...otherwise, try again
            logging.warning(
                f"Request failed (remaining retries: {retries_remaining}): "
                + reply.errorString()
            )
            self.make_request(url, callback, retries_remaining - 1)
            return

        # Parse the received message
        data: bytes = reply.readAll().data()
        callback(data.decode())
