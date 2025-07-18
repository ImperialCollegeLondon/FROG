"""Code for FROG's logs menu."""

import os

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QAction, QDesktopServices

from frog.logger import get_log_path


class LogOpen(QAction):
    """A menu option for opening the current log file."""

    def __init__(self, parent: QObject) -> None:
        """Create a menu item for opening the current log file.

        Args:
            parent: the menu on which to place the menu item
        """
        super().__init__("Open log", parent)
        self.triggered.connect(self.open_log)

    def open_log(self) -> None:
        """Opens the current log file."""
        from frog.logger import log_file

        QDesktopServices.openUrl(QUrl.fromLocalFile(log_file))


class LogLocationOpen(QAction):
    """A menu option for opening the log file folder location."""

    def __init__(self, parent: QObject) -> None:
        """Create a menu item for opening the log file folder location.

        Args:
            parent: the menu on which to place the menu item
        """
        super().__init__("Open file location", parent)
        self.triggered.connect(self.open_file_location)

    def open_file_location(self) -> None:
        """Opens the log file folder location."""
        path = os.path.realpath(get_log_path())
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
