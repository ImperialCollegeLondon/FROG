"""Provides a dialog to display the progress of a running measure script."""

from pubsub import pub
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QHideEvent, QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from frog.gui.measure_script.script import Script, ScriptRunner


def get_total_steps(script: Script) -> int:
    """Get the total number of steps that a measure script will require.

    Each Measurement is repeated n times, plus we have to move into position once per
    Measurement. The whole script is repeated m times.
    """
    return script.repeats * sum(1 + m.measurements for m in script.sequence)


class ScriptRunDialog(QDialog):
    """A dialog to display the progress of a running measure script."""

    def __init__(self, script_runner: ScriptRunner) -> None:
        """Create a new ScriptRunDialog.

        Args:
            script_runner: The ScriptRunner managing the current script
        """
        super().__init__()
        self.setWindowTitle("Running measure script")
        self.setModal(True)
        self.setMinimumSize(400, 100)

        # Keep a reference to prevent it being GC'd mid-run
        self._script_runner = script_runner

        self._stop_dlg = QMessageBox(
            QMessageBox.Icon.Warning,
            "Stop measure script?",
            "Do you want to cancel the currently running measure script?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            self,
        )
        """A dialog to let the user confirm whether they want to cancel the script."""
        self._stop_dlg.accepted.connect(self.reject)

        layout = QVBoxLayout()
        self._progress_bar = QProgressBar()
        """Shows the progress of the measure script."""
        self._progress_bar.setMaximum(get_total_steps(script_runner.script))
        layout.addWidget(self._progress_bar)

        self._label = QLabel()
        """A text label describing what the measure script is currently doing."""
        layout.addWidget(self._label)

        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setCheckable(True)
        self._pause_btn.clicked.connect(self._toggle_paused)

        buttonbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttonbox.addButton(self._pause_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttonbox.rejected.connect(self._stop_dlg.show)
        self.rejected.connect(lambda: pub.sendMessage("measure_script.abort"))
        layout.addWidget(buttonbox)

        self.setLayout(layout)

        # Update dialog when measure script changes state
        pub.subscribe(self._on_start_moving, "measure_script.start_moving")
        pub.subscribe(self._on_start_measuring, "measure_script.start_measuring")

    def _update(self, script_runner: ScriptRunner, text: str) -> None:
        """Increment the progress bar and update the QLabel."""
        self._progress_bar.setValue(self._progress_bar.value() + 1)
        self._label.setText(
            f"Repeat {script_runner.measurement_iter.current_repeat + 1}"
            f" of {script_runner.script.repeats}: {text}"
        )

    def _on_start_moving(self, script_runner: ScriptRunner) -> None:
        angle = script_runner.current_measurement.angle
        if isinstance(angle, float):
            angle = f"{round(angle)}°"
        self._update(script_runner, f"Moving to {angle}")

    def _on_start_measuring(self, script_runner: ScriptRunner) -> None:
        self._update(
            script_runner,
            f"Carrying out measurement {script_runner.current_measurement_count + 1}"
            f" of {script_runner.current_measurement.measurements}",
        )

    def _toggle_paused(self) -> None:
        """Toggle the pause state of the script."""
        if self._pause_btn.text() == "Pause":
            pub.sendMessage("measure_script.pause")
            self._pause_btn.setText("Unpause")
            self._progress_bar.setFormat("PAUSED (%p%)")
        else:
            pub.sendMessage("measure_script.unpause")
            self._progress_bar.setFormat("%p%")
            self._pause_btn.setText("Pause")

    def closeEvent(self, event: QCloseEvent) -> None:
        """Abort the measure script."""
        if self.isVisible():
            # Make the user confirm before cancelling measure script
            event.ignore()
            self._stop_dlg.show()

    def hideEvent(self, event: QHideEvent) -> None:
        """Hide the dialog."""
        super().hideEvent(event)
        self._stop_dlg.hide()

    def keyPressEvent(self, event: QKeyEvent):
        """Intercept when user presses escape to confirm whether to close dialog."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
