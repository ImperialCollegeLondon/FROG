"""A module with a single settings object for the program settings."""

from PySide6.QtCore import QSettings

from frog.config import APP_CONFIG_PATH

# We use platformdirs to choose the path for config file because Qt seems to use a
# slightly different scheme (at least on Linux)
settings = QSettings(str(APP_CONFIG_PATH / "settings.ini"), QSettings.Format.IniFormat)
"""Contains the program settings for FROG."""
