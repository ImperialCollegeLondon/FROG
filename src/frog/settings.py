"""A module with a single settings object for the program settings."""

from PySide6.QtCore import QSettings

from frog.config import APP_CONFIG_PATH

# We use platformdirs to choose the path for config file because Qt seems to use a
# slightly different scheme (at least on Linux)
settings = QSettings(str(APP_CONFIG_PATH / "settings.ini"), QSettings.Format.IniFormat)
"""Contains the program settings for FROG."""


def _checked[T](value: object, type: type[T], name: str) -> T:
    """Check that ``value`` is an instance of ``type``, returning it if so.

    Raises:
        TypeError: If ``value`` is not an instance of ``type``.
    """
    if not isinstance(value, type):
        raise TypeError(
            f"Setting {name!r} has type {value.__class__.__name__}, "
            f"expected {type.__name__}"
        )
    return value


def get_setting[T](type: type[T], name: str) -> T | None:
    """Get a value from the program settings.

    Args:
        type: The type the stored value is expected to have.
        name: The key under which the value is stored.

    Returns:
        The stored value, or ``None`` if the key is not present.

    Raises:
        TypeError: If the key is present but its value is not an instance of ``type``.
    """
    value = settings.value(name)
    if value is None:
        return None
    return _checked(value, type, name)


def get_setting_or_default[T](name: str, default: T) -> T:
    """Get a value from the program settings, falling back to a default.

    We check that the retrieved setting, if present, is the same type as ``default``.

    Args:
        name: The key under which the value is stored.
        default: The value to return if the key is not present.

    Returns:
        The stored value, or ``default`` if the key is not present.

    Raises:
        TypeError: If the key is present but its value's type differs from the
            default's type.
    """
    value = settings.value(name)
    if value is None:
        return default
    return _checked(value, type(default), name)
