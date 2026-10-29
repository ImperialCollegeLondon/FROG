"""A module with a single settings object for the program settings."""

import logging
from typing import Any

from PySide6.QtCore import QFile, QSettings

from frog.config import APP_CONFIG_PATH

# We use platformdirs to choose the path for config file because Qt seems to use a
# slightly different scheme (at least on Linux)
_settings = QSettings(str(APP_CONFIG_PATH / "settings.ini"), QSettings.Format.IniFormat)
"""Contains the program settings for FROG."""


def _trash_corrupted_settings_file(error: Exception) -> None:
    """Move the settings file to the recycle bin because it is corrupted.

    If the file cannot be moved to the recycle bin it will be overwritten the next
    time a setting is saved.

    Args:
        error: The exception that indicated the file is corrupted, logged to give the
            user more information about the type of corruption.
    """
    settings_path = _settings.fileName()
    logging.warning(
        f"Settings file at {settings_path} is corrupted ({error}). "
        "Moving to recycle bin."
    )
    if not QFile.moveToTrash(settings_path):
        logging.warning("Failed to move file to recycle bin. It will be overwritten.")

    # Wipe settings (in memory and eventually on disk, when Qt next flushes it)
    _settings.clear()


def get_setting[T](type: type[T], name: str) -> T | None:
    """Get a value from the program settings.

    A stored value whose type does not match ``type`` is treated as a corrupted
    settings file: the file is moved to the recycle bin and ``None`` is returned.

    Args:
        type: The type the stored value is expected to have.
        name: The key under which the value is stored.

    Returns:
        The stored value, or ``None`` if the key is not present (or the file was
        corrupted).
    """
    try:
        value = _settings.value(name)
        if value is None:
            # Setting not present
            return None

        if not isinstance(value, type):
            # Setting present, but of wrong type; something's gone wrong
            raise TypeError(
                f"Setting {name!r} has type {value.__class__.__name__}, "
                f"expected {type.__name__}"
            )

        return value
    except Exception as error:
        _trash_corrupted_settings_file(error)
        return None


def get_setting_or_default[T](name: str, default: T) -> T:
    """Get a value from the program settings, falling back to a default.

    The stored value, if present, is checked against the type of ``default``. A value
    of the wrong type is treated as a corrupted settings file: the file is moved to
    the recycle bin and ``default`` is returned.

    Args:
        name: The key under which the value is stored.
        default: The value to return if the key is not present.

    Returns:
        The stored value, or ``default`` if the key is not present (or the file was
        corrupted).
    """
    value = get_setting(type(default), name)
    return default if value is None else value


def set_setting(name: str, value: Any) -> None:
    """Store a value in the program settings.

    Args:
        name: The key under which to store the value.
        value: The value to store. Any type supported by :class:`QSettings` is allowed.
    """
    _settings.setValue(name, value)
