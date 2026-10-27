"""Tests for the settings helper functions."""

from unittest.mock import Mock, patch

import pytest
from PySide6.QtCore import QSettings

from frog.settings import get_setting, get_setting_or_default, set_setting


@pytest.fixture
def temp_settings(tmp_path):
    """Patch the global settings object with one backed by a temporary file."""
    qsettings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    with patch("frog.settings._settings", qsettings):
        yield qsettings


def test_get_setting_present(temp_settings: QSettings) -> None:
    """Test get_setting() returns a stored value of the expected type."""
    temp_settings.setValue("key", "hello")
    assert get_setting(str, "key") == "hello"


def test_get_setting_absent(temp_settings: QSettings) -> None:
    """Test get_setting() returns None when the key is not present."""
    assert get_setting(str, "missing") is None


@patch("frog.settings.QFile")
@patch("frog.settings._settings")
@patch("frog.settings.logging.warning")
def test_get_setting_wrong_type(
    warning_mock: Mock, settings_mock: Mock, qfile_mock: Mock
) -> None:
    """Test a stored value of an unexpected type is treated as a corrupted file."""
    settings_mock.value.return_value = "hello"
    settings_mock.fileName.return_value = "/path/to/settings.ini"
    qfile_mock.moveToTrash.return_value = True

    assert get_setting(int, "key") is None
    qfile_mock.moveToTrash.assert_called_once_with("/path/to/settings.ini")
    warning_mock.assert_called_once()


def test_get_setting_or_default_present(temp_settings: QSettings) -> None:
    """Test get_setting_or_default() returns a stored value if present."""
    temp_settings.setValue("key", "hello")
    assert get_setting_or_default("key", "default") == "hello"


def test_get_setting_or_default_absent(temp_settings: QSettings) -> None:
    """Test get_setting_or_default() returns the default when absent."""
    assert get_setting_or_default("missing", "default") == "default"


@patch("frog.settings.QFile")
@patch("frog.settings._settings")
@patch("frog.settings.logging.warning")
def test_get_setting_or_default_wrong_type(
    warning_mock: Mock, settings_mock: Mock, qfile_mock: Mock
) -> None:
    """Test a value whose type differs from the default is treated as corruption."""
    settings_mock.value.return_value = "hello"
    settings_mock.fileName.return_value = "/path/to/settings.ini"
    qfile_mock.moveToTrash.return_value = True

    assert get_setting_or_default("key", 5) == 5
    qfile_mock.moveToTrash.assert_called_once_with("/path/to/settings.ini")
    warning_mock.assert_called_once()


def test_set_setting(temp_settings: QSettings) -> None:
    """Test set_setting() stores a value in the settings."""
    set_setting("key", "hello")
    assert temp_settings.value("key") == "hello"


@patch("frog.settings.QFile")
@patch("frog.settings._settings")
@patch("frog.settings.logging.warning")
def test_get_setting_corrupted(
    warning_mock: Mock, settings_mock: Mock, qfile_mock: Mock
) -> None:
    """Test a corrupted settings file is moved to the recycle bin."""
    settings_mock.value.side_effect = Exception("corrupted")
    settings_mock.fileName.return_value = "/path/to/settings.ini"
    qfile_mock.moveToTrash.return_value = True

    # The setting is treated as absent
    assert get_setting(dict, "device/params/foo") is None

    # The file should have been moved to the recycle bin and a warning logged
    qfile_mock.moveToTrash.assert_called_once_with("/path/to/settings.ini")
    warning_mock.assert_called_once()


@patch("frog.settings.QFile")
@patch("frog.settings._settings")
@patch("frog.settings.logging.warning")
def test_get_setting_corrupted_move_fails(
    warning_mock: Mock, settings_mock: Mock, qfile_mock: Mock
) -> None:
    """Test the fallback when a corrupted settings file cannot be moved to trash."""
    settings_mock.value.side_effect = Exception("corrupted")
    settings_mock.fileName.return_value = "/path/to/settings.ini"
    qfile_mock.moveToTrash.return_value = False

    assert get_setting(dict, "device/params/foo") is None

    # An extra warning should be logged when the file can't be moved to the bin
    qfile_mock.moveToTrash.assert_called_once_with("/path/to/settings.ini")
    assert warning_mock.call_count == 2


@patch("frog.settings.QFile")
@patch("frog.settings._settings")
@patch("frog.settings.logging.warning")
def test_get_setting_or_default_corrupted(
    warning_mock: Mock, settings_mock: Mock, qfile_mock: Mock
) -> None:
    """Test get_setting_or_default() returns the default if the file is corrupted."""
    settings_mock.value.side_effect = Exception("corrupted")
    settings_mock.fileName.return_value = "/path/to/settings.ini"
    qfile_mock.moveToTrash.return_value = True

    assert get_setting_or_default("key", "default") == "default"
    qfile_mock.moveToTrash.assert_called_once_with("/path/to/settings.ini")
    warning_mock.assert_called_once()
