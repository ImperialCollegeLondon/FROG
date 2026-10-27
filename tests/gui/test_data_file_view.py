"""Tests for DataFileControl."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

import pytest
from freezegun import freeze_time

from frog.gui.data_file_view import DataFileControl

FILE_PATH = Path("/path/to/file.csv")
TEST_DATETIME = datetime(2024, 1, 1)
"""Fix system time for time-dependent unit tests."""


@pytest.fixture
def data_file(subscribe_mock: MagicMock, qtbot) -> DataFileControl:
    """Provides a DataFileControl."""
    return DataFileControl()


@patch.object(DataFileControl, "_try_start_recording")
def test_init(
    start_mock: MagicMock, subscribe_mock: MagicMock, sendmsg_mock: MagicMock, qtbot
) -> None:
    """Test DataFileControl's constructor."""
    data_file = DataFileControl()
    assert data_file._open_dir_widget.isEnabled()
    assert data_file._filename_prefix_widget.isEnabled()

    subscribe_mock.assert_any_call(data_file._on_file_open, "data_file.opened")
    subscribe_mock.assert_any_call(data_file._on_file_close, "data_file.close")
    subscribe_mock.assert_any_call(data_file._show_error_message, "data_file.error")

    start_mock.assert_not_called()
    data_file._record_widget.start_recording.emit()
    start_mock.assert_called_once_with()

    sendmsg_mock.assert_not_called()
    data_file._record_widget.stop_recording.emit()
    sendmsg_mock.assert_called_once_with("data_file.close")


@patch("frog.gui.data_file_view.set_setting")
def test_save_file_path_settings(
    set_setting_mock: Mock, data_file: DataFileControl, qtbot
) -> None:
    """Test the _save_file_path_settings() method."""
    data_file._open_dir_widget.line_edit.setText("/some/path")
    data_file._filename_prefix_widget.setText("some_prefix")
    data_file._save_file_path_settings()
    set_setting_mock.assert_has_calls(
        (
            call("data/destination_dir", "/some/path"),
            call("data/filename_prefix", "some_prefix"),
        )
    )


def test_on_file_open(data_file: DataFileControl, qtbot) -> None:
    """Test the _on_file_open() method."""
    with patch.object(data_file, "_save_file_path_settings") as save_mock:
        data_file._open_dir_widget.setEnabled(True)
        data_file._filename_prefix_widget.setEnabled(True)
        data_file._on_file_open()
        assert not data_file._open_dir_widget.isEnabled()
        assert not data_file._filename_prefix_widget.isEnabled()
        save_mock.assert_called_once_with()


def test_on_file_close(data_file: DataFileControl, qtbot) -> None:
    """Test the _on_file_close() method."""
    data_file._open_dir_widget.setEnabled(False)
    data_file._filename_prefix_widget.setEnabled(False)
    data_file._on_file_close()
    assert data_file._open_dir_widget.isEnabled()
    assert data_file._filename_prefix_widget.isEnabled()


@freeze_time(TEST_DATETIME)
def test_try_get_data_file_path_success(
    data_file: DataFileControl, tmp_path: Path, qtbot
) -> None:
    """Test the _try_get_data_path() method when everything succeeds."""
    data_file._filename_prefix_widget.setText("some_prefix")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    expected_path = tmp_path / f"some_prefix_{timestamp}.csv"

    with patch.object(
        data_file._open_dir_widget, "try_get_path", return_value=tmp_path
    ):
        assert data_file._try_get_data_file_path() == expected_path


def test_try_get_data_file_path_no_data_dir(data_file: DataFileControl, qtbot) -> None:
    """Test the _try_get_data_path() method when data dir not chosen."""
    data_file._filename_prefix_widget.setText("some_prefix")
    with patch.object(data_file._open_dir_widget, "try_get_path", return_value=None):
        assert data_file._try_get_data_file_path() is None


@patch("frog.gui.data_file_view.QMessageBox")
def test_try_get_data_file_path_no_filename_prefix(
    msgbox_mock: Mock, data_file: DataFileControl, tmp_path: Path, qtbot
) -> None:
    """Test the _try_get_data_path() method when filename prefix not entered."""
    data_file._filename_prefix_widget.setText("")
    with patch.object(
        data_file._open_dir_widget, "try_get_path", return_value=tmp_path
    ):
        assert data_file._try_get_data_file_path() is None
        msgbox_mock.assert_called_once()


@freeze_time(TEST_DATETIME)
@patch("frog.gui.data_file_view.QMessageBox")
def test_try_get_data_file_path_file_exists(
    msgbox_mock: Mock, data_file: DataFileControl, tmp_path: Path, qtbot
) -> None:
    """Test the _try_get_data_path() method when the file already exists."""
    data_file._filename_prefix_widget.setText("some_prefix")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    expected_path = tmp_path / f"some_prefix_{timestamp}.csv"
    expected_path.open("a").close()  # create file

    with patch.object(
        data_file._open_dir_widget, "try_get_path", return_value=tmp_path
    ):
        assert data_file._try_get_data_file_path() is None
        msgbox_mock.assert_called_once()


def test_try_start_recording_success(
    data_file: DataFileControl, sendmsg_mock: Mock, qtbot
) -> None:
    """Test that _try_start_recording() sends a pubsub message on success."""
    path = MagicMock()  # mock path
    with patch.object(data_file, "_try_get_data_file_path", return_value=path):
        data_file._try_start_recording()
        sendmsg_mock.assert_called_once_with("data_file.open", path=path)


def test_try_start_recording_fail(
    data_file: DataFileControl, sendmsg_mock: Mock, qtbot
) -> None:
    """Test that _try_start_recording() doesn't send pubsub message on failure."""
    with patch.object(data_file, "_try_get_data_file_path", return_value=None):
        data_file._try_start_recording()
        sendmsg_mock.assert_not_called()


@patch("frog.gui.data_file_view.QMessageBox")
def test_show_error_message(
    msgbox_mock: Mock, data_file: DataFileControl, qtbot
) -> None:
    """Test the _show_error_message() method."""
    msgbox_mock.return_value = msgbox = MagicMock()
    error = Exception()
    data_file._show_error_message(error)
    msgbox_mock.assert_called_once_with(
        msgbox_mock.Icon.Critical,
        "Error writing to file",
        f"An error occurred while writing the data file: {error!s}",
        msgbox_mock.StandardButton.Ok,
        data_file,
    )
    msgbox.exec.assert_called_once_with()
