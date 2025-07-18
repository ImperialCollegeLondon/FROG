"""The main module for the FROG program."""

from frog.config import APP_VERSION

__version__ = APP_VERSION


def run() -> None:
    """Run FROG."""
    import sys

    from PySide6.QtWidgets import QApplication

    # This must be done before our own modules are imported
    from frog.logger import initialise_logging

    initialise_logging()

    from frog import hardware  # noqa
    from frog.gui.main_window import MainWindow

    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    app.exec()
