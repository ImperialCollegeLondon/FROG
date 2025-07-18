"""For showing error messages."""

import logging

from PySide6.QtWidgets import QMessageBox, QWidget


def show_error_message(
    parent: QWidget | None, msg: str, title="An error has occurred"
) -> None:
    """Show an error message in the GUI and write to the program log."""
    # Show popup box in GUI
    msg_box = QMessageBox(
        QMessageBox.Icon.Critical,
        title,
        msg,
        QMessageBox.StandardButton.Ok,
        parent,
    )
    msg_box.exec()

    # Write to program log
    logging.error(msg)
