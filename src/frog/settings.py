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


def get_setting(name: str, type: type | None = None, default: Any = None) -> Any:
    """Get a value from the program settings.

    Either the `type` parameter or `default` parameter must be given (or both).

    A stored value whose type does not match the expected type is treated as a
    corrupted settings file: the file is moved to the recycle bin and ``default`` (or
    ``None`` if not given) is returned.

    Args:
        name: The key under which the value is stored.
        type: The type the stored value is expected to have. If omitted, the type of
            ``default`` is used.
        default: The value to return if the key is not present.

    Returns:
        The stored value, or ``default`` if the key is not present (or the file was
        corrupted).

    Raises:
        TypeError: If neither ``type`` nor ``default`` is given, or ``default`` is not
            an instance of ``type``.
    """
    if type is None:
        if default is None:
            raise TypeError("At least one of type and default must be given")
        type = default.__class__
    elif default is not None and not isinstance(default, type):
        raise TypeError(
            f"Default value has type {default.__class__.__name__}, "
            f"expected {type.__name__}"
        )

    try:
        value = _settings.value(name)
        if value is None:
            # Setting not present
            return default

        if not isinstance(value, type):
            # Setting present, but of wrong type; something's gone wrong
            raise TypeError(
                f"Setting {name!r} has type {value.__class__.__name__}, "
                f"expected {type.__name__}"
            )

        return value
    except Exception as error:
        _trash_corrupted_settings_file(error)
        return default


def set_setting(name: str, value: Any) -> None:
    """Store a value in the program settings.

    Args:
        name: The key under which to store the value.
        value: The value to store. Any type supported by :class:`QSettings` is allowed.
    """
    _settings.setValue(name, value)
