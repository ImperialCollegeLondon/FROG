"""Code for handling uncaught exceptions."""

import logging
import sys
import traceback
from functools import partial
from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


def set_uncaught_exception_handler(parent: QWidget) -> None:
    """Catches uncaught exceptions so we can log them and display a dialog.

    Details of the exception, including the stack trace, will be written to the program
    log and displayed to the user in a pop-up dialog. Note that this won't happen if
    you're running the program in a debugger that intercepts these exceptions first!

    The purpose is to make it easier for end-users to communicate with the developers
    when a bug occurs.
    """
    sys.excepthook = partial(_handle_exception, parent)


def _handle_exception(
    parent: QWidget,
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: Any,
) -> None:
    """Handle an uncaught exception."""
    # Don't do anything special if user has just pressed Ctrl+C
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    traceback_str = "".join(
        traceback.format_exception(exc_type, exc_value, exc_traceback)
    )

    # Write to program log
    logging.error(f"Unhandled error:\n{traceback_str}")

    try:
        # Also show a message box for the user
        _show_uncaught_exception_dialog(parent, exc_value, traceback_str)
    except Exception:
        # Something may go wrong with displaying the dialog, e.g. if the QApplication is
        # shutting down, but we don't care at this point as it has been logged anyway
        pass


def _show_uncaught_exception_dialog(
    parent: QWidget, exc_value: BaseException, traceback_str: str
) -> None:
    """Show a dialog containing information about an exception."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Uncaught exception")
    dialog.resize(700, 500)

    label = QLabel(f"An unhandled error has occurred: {exc_value!r}")
    textEdit = QPlainTextEdit(traceback_str)
    textEdit.setReadOnly(True)
    buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
    buttonBox.setCenterButtons(True)
    buttonBox.accepted.connect(dialog.accept)

    layout = QVBoxLayout()
    layout.addWidget(label)
    layout.addWidget(textEdit)
    layout.addWidget(buttonBox)

    dialog.setLayout(layout)
    dialog.exec()
