"""Provides a panel which lets the user start and stop recording of data files."""

from pathlib import Path
from typing import cast

from pubsub import pub
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from frog.config import DEFAULT_DATA_FILE_PATH
from frog.gui.led_icon import LEDIcon
from frog.gui.path_widget import OpenDirectoryWidget
from frog.hardware.plugins.time import get_current_time
from frog.settings import settings


def _get_previous_destination_dir() -> Path:
    path = cast(str, settings.value("data/destination_dir", ""))
    return Path(path) if path else DEFAULT_DATA_FILE_PATH


def _get_previous_filename_prefix() -> str:
    return cast(str, settings.value("data/filename_prefix", "data"))


class RecordingWidget(QWidget):
    """A widget to start/stop recording and display recording status.

    When the user clicks the button to start/stop recording the start_recording or
    stop_recording signals, respectively, are triggered.

    Whether or not data is currently being recorded is shown by a text label and a
    flashing LED indicator.
    """

    start_recording = Signal()
    stop_recording = Signal()

    def __init__(self) -> None:
        """Create a new RecordingWidget."""
        super().__init__()

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self._led = LEDIcon.create_red_icon()
        """Icon to indicate whether recording is taking place."""
        pub.subscribe(self._led.flash, "data_file.writing")
        layout.addWidget(self._led)

        self._label = QLabel("NOT RECORDING")
        """Label to show recording status."""
        # Put a margin on the right so that the button isn't too close
        self._label.setContentsMargins(0, 0, 50, 0)
        layout.addWidget(self._label)

        self._btn = QPushButton("Start recording")
        """Send signal to start/stop recording."""
        self._btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self._btn.clicked.connect(self._on_button_clicked)
        layout.addWidget(self._btn)

        self._is_recording = False
        """Whether data is being recorded."""

        # Update widget on file open/close
        pub.subscribe(self._on_file_open, "data_file.opened")
        pub.subscribe(self._on_file_close, "data_file.close")

    def _on_file_open(self) -> None:
        """Update widget when recording starts."""
        self._is_recording = True
        self._btn.setText("Stop recording")
        self._label.setText('<font color="red"><b>RECORDING IN PROGRESS</b></font>')

    def _on_file_close(self) -> None:
        """Update widget when recording stops."""
        self._is_recording = False
        self._btn.setText("Start recording")
        self._label.setText("NOT RECORDING")

    def _on_button_clicked(self) -> None:
        if self._is_recording:
            self.stop_recording.emit()
        else:
            self.start_recording.emit()


class DataFileControl(QGroupBox):
    """A panel which lets the user start and stop recording of data files."""

    def __init__(self) -> None:
        """Create a new DataFileControl."""
        super().__init__("Data file")

        layout = QGridLayout()

        self._open_dir_widget = OpenDirectoryWidget(
            parent=self,
            caption="Choose destination for data file",
            dir=str(DEFAULT_DATA_FILE_PATH),
        )
        """Lets the user choose the destination for data files."""
        self._open_dir_widget.set_path(_get_previous_destination_dir())
        layout.addWidget(QLabel("Destination directory:"), 0, 0)
        layout.addWidget(self._open_dir_widget, 0, 1)

        layout.addWidget(QLabel("Filename prefix:"), 1, 0)

        self._filename_prefix_widget = QLineEdit()
        self._filename_prefix_widget.setText(_get_previous_filename_prefix())
        layout.addWidget(self._filename_prefix_widget, 1, 1)

        self._record_widget = RecordingWidget()
        self._record_widget.start_recording.connect(self._try_start_recording)
        self._record_widget.stop_recording.connect(
            lambda: pub.sendMessage("data_file.close")
        )
        self._record_widget.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum
        )
        layout.addWidget(self._record_widget, 2, 0, 1, 2, Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)

        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        # Update GUI on file open/close
        pub.subscribe(self._on_file_open, "data_file.opened")
        pub.subscribe(self._on_file_close, "data_file.close")

        # Show an error message if writing fails
        pub.subscribe(self._show_error_message, "data_file.error")

    def _on_file_open(self) -> None:
        self._open_dir_widget.setEnabled(False)
        self._filename_prefix_widget.setEnabled(False)
        self._save_file_path_settings()

    def _save_file_path_settings(self) -> None:
        """Save the current destination dir and filename prefix to program settings."""
        settings.setValue(
            "data/destination_dir", self._open_dir_widget.line_edit.text()
        )
        settings.setValue("data/filename_prefix", self._filename_prefix_widget.text())

    def _on_file_close(self) -> None:
        self._open_dir_widget.setEnabled(True)
        self._filename_prefix_widget.setEnabled(True)

    def _try_get_data_file_path(self) -> Path | None:
        dest_dir = self._open_dir_widget.try_get_path()
        if not dest_dir:
            # User cancelled
            return None

        filename_prefix = self._filename_prefix_widget.text()
        if not filename_prefix:
            # Check that the user has added a prefix
            QMessageBox(
                QMessageBox.Icon.Critical,
                "No filename prefix specified",
                "The filename prefix cannot be blank.",
            ).exec()
            return None

        timestamp = get_current_time().strftime("%Y%m%d_%H%M%S")
        path = dest_dir / f"{filename_prefix}_{timestamp}.csv"
        if path.exists():
            # It's unlikely that the file will already exist, but let's make doubly sure
            QMessageBox(
                QMessageBox.Icon.Critical,
                "File already exists",
                "The destination file already exists.",
            ).exec()
            return None

        return path

    def _try_start_recording(self) -> None:
        """Starts recording if the user has provided a data path."""
        if path := self._try_get_data_file_path():
            pub.sendMessage("data_file.open", path=path)

    def _show_error_message(self, error: BaseException) -> None:
        """Show an error dialog."""
        msg_box = QMessageBox(
            QMessageBox.Icon.Critical,
            "Error writing to file",
            f"An error occurred while writing the data file: {error!s}",
            QMessageBox.StandardButton.Ok,
            self,
        )
        msg_box.exec()
