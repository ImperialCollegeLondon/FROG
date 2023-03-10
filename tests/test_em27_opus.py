"""Tests for the interface to the EM27's OPUS control program."""
from typing import Any, Optional
from unittest.mock import MagicMock, Mock, patch

import pytest

from finesse.config import OPUS_IP
from finesse.hardware.em27_opus import OPUSInterface, OPUSRequester


@pytest.fixture
@patch("finesse.hardware.em27_opus.QThread.start")
def opus(mock) -> OPUSInterface:
    """Fixture for OPUSInterface."""
    return OPUSInterface()


def test_request_status(opus: OPUSInterface) -> None:
    """Test OPUSInterface's request_status() method."""
    with patch.object(opus, "submit_request") as request_mock:
        opus.request_command("status")
        request_mock.emit.assert_called_once_with("stat.htm", "opus.response.status")


def test_request_command(opus: OPUSInterface) -> None:
    """Test OPUSInterface's request_command() method."""
    with patch.object(opus, "submit_request") as request_mock:
        opus.request_command("hello")
        request_mock.emit.assert_called_once_with(
            "cmd.htm?opusrshello", "opus.response.hello"
        )


@patch("finesse.hardware.em27_opus.requests")
def test_make_request_success(requests_mock) -> None:
    """Test OPUSRequester's make_request() method with a successful request."""
    requester = OPUSRequester(5.0)

    with patch.object(requester, "request_complete") as request_complete_mock:
        filename = "filename"
        topic = "topic"
        requests_mock.get.return_value = "MAGIC"
        requester.make_request(filename, topic)
        requests_mock.get.assert_called_once_with(
            f"http://{OPUS_IP}/opusrs/{filename}", timeout=5.0
        )

        request_complete_mock.emit.assert_called_once_with("MAGIC", topic)


@patch("finesse.hardware.em27_opus.requests")
def test_make_request_error(requests_mock) -> None:
    """Test OPUSRequester's make_request() method with failed request."""
    requester = OPUSRequester(5.0)
    error = RuntimeError("Request failed")
    requests_mock.get.side_effect = error

    with patch.object(requester, "request_error") as request_error_mock:
        filename = "filename"
        topic = "topic"
        requests_mock.get.return_value = "MAGIC"
        requester.make_request(filename, topic)
        requests_mock.get.assert_called_once_with(
            f"http://{OPUS_IP}/opusrs/{filename}", timeout=5.0
        )

        request_error_mock.emit.assert_called_once_with(error)


def _format_td(name: str, value: Any) -> str:
    if value is None:
        return ""
    return f'<td id="{name}">{str(value)}</td>'


def _get_opus_html(
    status: Optional[int],
    text: Optional[str],
    errcode: Optional[int],
    errtext: Optional[str],
    extra_text: str = "",
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


def _get_opus_response(http_status_code: int, *args: Any, **kwargs: Any) -> MagicMock:
    """Mock a requests.Response."""
    html = _get_opus_html(*args, **kwargs)
    response = MagicMock()
    response.status_code = http_status_code
    response.url = "https://example.com"
    response.content = html.encode()
    return response


@pytest.mark.parametrize(
    "status,text,errcode,errtext",
    (
        (status, text, errcode, errtext)
        for status in (None, 0, 1)
        for text in (None, "", "status text")
        for errcode in (None, 0, 1)
        for errtext in (None, "", "error text")
    ),
)
def test_parse_response(
    status: Optional[int],
    text: Optional[str],
    errcode: Optional[int],
    errtext: Optional[str],
    opus: OPUSInterface,
    sendmsg_mock: MagicMock,
) -> None:
    """Test the _parse_response() method."""
    response = _get_opus_response(200, status, text, errcode, errtext)

    with patch.object(opus, "error_occurred") as error_mock:
        opus._parse_response(response, "my.topic")
        if status is None or text is None:
            # Required fields missing
            error_mock.assert_called()
        else:
            error = None if errcode is None else (errcode, errtext)
            sendmsg_mock.assert_called_once_with(
                "my.topic", url=response.url, status=status, text=text, error=error
            )
            error_mock.assert_not_called()


def test_parse_response_no_id(opus: OPUSInterface) -> None:
    """Test that _parse_response() can handle <td> tags without an id."""
    response = _get_opus_response(200, 1, "text", 1, "errtext", "<td>something</td>")

    with patch.object(opus, "error_occurred") as error_mock:
        opus._parse_response(response, "my.topic")
        error_mock.assert_not_called()


@patch("finesse.hardware.em27_opus.logging.warning")
def test_parse_response_bad_id(warning_mock: Mock, opus: OPUSInterface) -> None:
    """Test that _parse_response() can handle <td> tags with unexpected id values."""
    response = _get_opus_response(
        200, 1, "text", 1, "errtext", '<td id="MADE_UP">something</td>'
    )

    with patch.object(opus, "error_occurred") as error_mock:
        opus._parse_response(response, "my.topic")
        error_mock.assert_not_called()
        warning_mock.assert_called()


@pytest.mark.parametrize("http_status_code", (200, 403, 404))
def test_parse_response_http_status(http_status_code: int, opus: OPUSInterface) -> None:
    """Test that _parse_response() handles HTTP status codes correctly."""
    response = _get_opus_response(http_status_code, 1, "text", 1, "errtext")

    with patch.object(opus, "error_occurred") as error_mock:
        opus._parse_response(response, "my.topic")
        if http_status_code == 200:
            error_mock.assert_not_called()
        else:
            error_mock.assert_called()
