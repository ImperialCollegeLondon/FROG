"""Tests for the interface to the EM27's OPUS control program."""

from itertools import product
from typing import Any
from unittest.mock import ANY, MagicMock, Mock, patch

import pytest
from PySide6.QtNetwork import QNetworkReply

from frog.config import DEFAULT_OPUS_HOST, DEFAULT_OPUS_PORT
from frog.hardware.plugins.spectrometer.opus_interface import (
    OPUSError,
    OPUSInterface,
    parse_response,
)
from frog.spectrometer_status import SpectrometerStatus


@pytest.fixture
def opus(qtbot) -> OPUSInterface:
    """Fixture for OPUSInterface."""
    return OPUSInterface()


@patch("frog.hardware.plugins.spectrometer.opus_interface.OPUSInterfaceBase.subscribe")
@patch("frog.hardware.plugins.spectrometer.opus_interface.QTimer")
def test_init(timer_mock: Mock, subscribe_mock: Mock) -> None:
    """Test the constructor."""
    timer = MagicMock()
    timer_mock.return_value = timer

    with patch.object(OPUSInterface, "_request_status") as status_mock:
        opus = OPUSInterface()
        assert opus._url == f"http://{DEFAULT_OPUS_HOST}:{DEFAULT_OPUS_PORT}/opusrs"
        status_mock.assert_called_once_with()

        assert opus._status is None
        timer.setSingleShot.assert_called_once_with(True)
        timer.setInterval.assert_called_once_with(1000)
        timer.timeout.connect.assert_called_once_with(opus._request_status)


def test_request_status(opus: OPUSInterface, qtbot) -> None:
    """Test OPUSInterface's _request_status() method."""
    with patch.object(opus, "_make_request") as request_mock:
        opus._request_status()
        request_mock.assert_called_once_with("stat.htm")


@pytest.mark.parametrize("command", ("connect", "start", "stop", "cancel"))
def test_request_command(command: str, opus: OPUSInterface, qtbot) -> None:
    """Test OPUSInterface's request_command() method."""
    with patch.object(opus, "_make_request") as request_mock:
        opus.request_command(command)
        request_mock.assert_called_once_with(f"cmd.htm?opusrs{command}")


@pytest.mark.parametrize("filename", ("hello.htm", "hello.htm?somequery"))
def test_make_request(opus: OPUSInterface, filename: str, qtbot) -> None:
    """Test OPUSInterface's request_command() method."""
    with patch.object(opus, "_requester") as requester_mock:
        opus._make_opus_request(filename)
        requester_mock.make_request.assert_called_once_with(
            f"http://{DEFAULT_OPUS_HOST}:{DEFAULT_OPUS_PORT}/opusrs/{filename}", ANY
        )


def _format_td(name: str, value: Any) -> str:
    if value is None:
        return ""
    return f'<td id="{name}">{value!s}</td>'


def _get_opus_html(
    status: int | None,
    errcode: int | None = None,
    errtext: str | None = None,
    extra_text: str = "",
    text: str | None = "status text",
) -> str:
    return f"""
    <html>
        <body>
            <table>
                <tr>
                    {extra_text}
                    {_format_td("STATUS", status)}
                    {_format_td("TEXT", text)}
                    {_format_td("ERRCODE", errcode)}
                    {_format_td("ERRTEXT", errtext)}
                </tr>
            </table>
        </body>
    </html>
    """


@pytest.mark.parametrize(
    "status", (SpectrometerStatus.IDLE, SpectrometerStatus.CONNECTING)
)
def test_parse_response_no_error(status: SpectrometerStatus) -> None:
    """Test parse_response() works when no error has occurred."""
    response = _get_opus_html(status.value)
    assert parse_response(response) == status


@pytest.mark.parametrize("errcode,errtext", product(range(2), ("", "error text")))
def test_parse_response_error(errcode: int, errtext: str) -> None:
    """Test parse_response() works when an error has occurred."""
    response = _get_opus_html(SpectrometerStatus.CONNECTING.value, errcode, errtext)
    with pytest.raises(OPUSError):
        parse_response(response)


@pytest.mark.parametrize("status,text", ((None, "text"), (1, None), (None, None)))
def test_parse_response_missing_fields(status: int | None, text: str | None) -> None:
    """Test parse_response() raises an error if fields are missing."""
    response = _get_opus_html(status, text=text)
    with pytest.raises(OPUSError):
        parse_response(response)


def test_parse_response_no_id(opus: OPUSInterface) -> None:
    """Test that parse_response() can handle <td> tags without an id."""
    response = _get_opus_html(
        SpectrometerStatus.CONNECTING.value, 1, "errtext", "<td>something</td>"
    )
    with pytest.raises(OPUSError):
        parse_response(response)


@patch("frog.hardware.plugins.spectrometer.opus_interface.logging.warning")
def test_parse_response_bad_id(warning_mock: Mock) -> None:
    """Test that parse_response() can handle <td> tags with unexpected id values."""
    response = _get_opus_html(
        SpectrometerStatus.CONNECTING.value,
        1,
        "errtext",
        '<td id="MADE_UP">something</td>',
    )
    with pytest.raises(OPUSError):
        parse_response(response)
    warning_mock.assert_called()


@patch("frog.hardware.plugins.spectrometer.opus_interface.parse_response")
def test_on_reply_received_status_changed(
    parse_response_mock: Mock, opus: OPUSInterface, qtbot
) -> None:
    """Test the _on_reply_received() method works when no error occurs."""
    reply = MagicMock()
    reply.error.return_value = QNetworkReply.NetworkError.NoError

    assert opus._status != SpectrometerStatus.CONNECTED
    parse_response_mock.return_value = SpectrometerStatus.CONNECTED

    # Check the status update is sent
    with patch.object(opus, "send_status_message") as status_mock:
        opus._on_reply_received(reply)
        assert opus._status == SpectrometerStatus.CONNECTED
        status_mock.assert_called_once_with(SpectrometerStatus.CONNECTED)


@patch("frog.hardware.plugins.spectrometer.opus_interface.parse_response")
def test_on_reply_received_status_unchanged(
    parse_response_mock: Mock, opus: OPUSInterface, qtbot
) -> None:
    """Test the _on_reply_received() method only sends a status update if changed."""
    reply = MagicMock()
    reply.error.return_value = QNetworkReply.NetworkError.NoError

    opus._status = SpectrometerStatus.CONNECTED
    parse_response_mock.return_value = SpectrometerStatus.CONNECTED

    # Check the status is send
    with patch.object(opus, "send_status_message") as status_mock:
        opus._on_reply_received(reply)
        status_mock.assert_not_called()


@patch("frog.hardware.plugins.spectrometer.opus_interface.parse_response")
def test_on_reply_received_network_error(
    parse_response_mock: Mock, opus: OPUSInterface, qtbot
) -> None:
    """Test the _on_reply_received() method handles network errors."""
    reply = MagicMock()
    reply.error.return_value = QNetworkReply.NetworkError.HostNotFoundError
    reply.errorString.return_value = "Something went wrong"

    with pytest.raises(OPUSError):
        opus._on_reply_received(reply)


@patch("frog.hardware.plugins.spectrometer.opus_interface.parse_response")
def test_on_reply_received_exception(
    parse_response_mock: Mock, opus: OPUSInterface, qtbot
) -> None:
    """Test that the _on_reply_received() method catches parsing errors."""
    reply = MagicMock()
    reply.error.return_value = QNetworkReply.NetworkError.NoError

    # Make parse_response() raise an exception
    parse_response_mock.side_effect = RuntimeError

    with pytest.raises(RuntimeError):
        opus._on_reply_received(reply)
