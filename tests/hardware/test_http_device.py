"""Tests for the HTTPDevice class."""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtNetwork import QNetworkReply

from frog.hardware.http_device import HTTPDevice


class MockHTTPDevice(HTTPDevice):
    """Concrete implementation of HTTPDevice for testing purposes."""

    def handle_response(self, response: str) -> None:
        """Mock implementation of handle_response."""

    def close(self) -> None:
        """Mock implementation of device close."""


@pytest.fixture
def http_device(qtbot):
    """Fixture to create an instance of TestHTTPDevice."""
    yield MockHTTPDevice(timeout=5)


def test_http_device_initialisation():
    """Test initialisation of HTTPDevice."""
    device = MockHTTPDevice(timeout=10)
    assert device._timeout == 10


def test_http_device_invalid_timeout():
    """Test that HTTPDevice raises an error for invalid timeout."""
    with pytest.raises(ValueError, match="Timeout must be greater than zero"):
        MockHTTPDevice(timeout=0)


def test_make_request(http_device: HTTPDevice):
    """Test the make_request method."""
    with patch.object(http_device, "_manager") as mock_manager:
        mock_reply = MagicMock(spec=QNetworkReply)
        mock_manager.get.return_value = mock_reply

        callback = MagicMock()
        url = "http://example.com"
        http_device.make_request(url, callback)

        mock_manager.get.assert_called_once()
        mock_reply.finished.connect.assert_called_once()


def test_on_reply_received_success(http_device: HTTPDevice):
    """Test _on_reply_received with a successful reply."""
    mock_reply = MagicMock()
    mock_reply.error.return_value = QNetworkReply.NetworkError.NoError
    mock_reply.readAll().data.return_value = b"response data"
    callback = MagicMock()

    http_device._on_reply_received(mock_reply, callback)

    callback.assert_called_once_with("response data")


def test_on_reply_received_error(http_device: HTTPDevice):
    """Test _on_reply_received with a network error."""
    mock_reply = MagicMock()
    mock_reply.error.return_value = QNetworkReply.NetworkError.ContentNotFoundError
    mock_reply.errorString.return_value = "404 Not Found"

    with pytest.raises(RuntimeError, match="Network error: 404 Not Found"):
        http_device._on_reply_received(mock_reply, MagicMock())
