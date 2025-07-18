"""Contains a panel for loading and editing measure scripts."""

from pathlib import Path
from typing import cast

from pubsub import pub
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QMessageBox,
    QPushButton,
)

from frog.config import DEFAULT_SCRIPT_PATH, SPECTROMETER_TOPIC, STEPPER_MOTOR_TOPIC
from frog.device_info import DeviceInstanceRef
from frog.gui.event_counter import EventCounter
from frog.gui.measure_script.script import Script, ScriptRunner
from frog.gui.measure_script.script_edit_dialog import ScriptEditDialog
from frog.gui.measure_script.script_run_dialog import ScriptRunDialog
from frog.gui.path_widget import OpenFileWidget
from frog.settings import settings
from frog.spectrometer_status import SpectrometerStatus


def _get_previous_script_path() -> Path | None:
    path = cast(str, settings.value("script/run_path", ""))
    return Path(path) if path else None


class ScriptControl(QGroupBox):
    """A panel for loading and editing measure scripts."""

    def __init__(self) -> None:
        """Create a new ScriptControl."""
        super().__init__("Script control")

        create_btn = QPushButton("Create new script")
        create_btn.clicked.connect(self._create_btn_clicked)

        edit_btn = QPushButton("Edit script")
        edit_btn.clicked.connect(self._edit_btn_clicked)

        self.script_path = OpenFileWidget(
            initial_file_path=_get_previous_script_path(),
            extension="yaml",
            parent=self,
            caption="Choose measure script to load",
            dir=str(DEFAULT_SCRIPT_PATH),
        )

        run_btn = QPushButton("Run script")
        run_btn.clicked.connect(self._run_btn_clicked)
        run_btn.setEnabled(False)

        self._enable_counter = EventCounter(
            lambda: run_btn.setEnabled(True),
            lambda: run_btn.setEnabled(False),
            target_count=2,
            device_names=(STEPPER_MOTOR_TOPIC,),
        )
        """A counter to enable/disable the "Run" button."""

        layout = QGridLayout()
        layout.addWidget(create_btn, 0, 0)
        layout.addWidget(edit_btn, 0, 1)
        layout.addWidget(self.script_path, 1, 0)
        layout.addWidget(run_btn, 1, 1)
        self.setLayout(layout)

        # Enable the run button when the spectrometer is connected and not already
        # measuring and disable otherwise
        self._spectrometer_ready = False
        pub.subscribe(
            self._on_spectrometer_status_changed,
            f"device.{SPECTROMETER_TOPIC}.status",
        )
        pub.subscribe(
            self._on_spectrometer_disconnect, f"device.closed.{SPECTROMETER_TOPIC}"
        )

        # Show/hide self.run_dialog on measure script begin/end
        pub.subscribe(self._show_run_dialog, "measure_script.begin")
        pub.subscribe(self._hide_run_dialog, "measure_script.end")

        # Keep track of whether recording is taking place, so we can remind user to
        # start recording
        pub.subscribe(self._on_recording_start, "data_file.opened")
        pub.subscribe(self._on_recording_stop, "data_file.close")
        self._data_file_recording = False
        """Whether data file is currently being recorded."""

        self.edit_dialog: ScriptEditDialog
        """A dialog for editing the contents of a measure script."""

        self.run_dialog: ScriptRunDialog
        """A dialog showing the progress of a running measure script."""

    def _on_recording_start(self) -> None:
        self._data_file_recording = True

    def _on_recording_stop(self) -> None:
        self._data_file_recording = False

    def _create_btn_clicked(self) -> None:
        self.edit_dialog = ScriptEditDialog()
        self.edit_dialog.show()

    def _edit_btn_clicked(self) -> None:
        # Ask user to choose script file to edit
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            caption="Choose script file to edit",
            dir=str(DEFAULT_SCRIPT_PATH),
            filter="*.yaml",
        )
        if not file_path:
            # User closed dialog
            return

        script = Script.try_load(self, Path(file_path))
        if not script:
            # An error occurred while loading script
            return

        # Create new dialog showing contents of script
        self.edit_dialog = ScriptEditDialog(script)
        self.edit_dialog.show()

    def _check_data_file_recording(self) -> bool:
        """Check whether recording is in progress and user is happy to continue.

        This reminds the user that they may want to start recording a data file before
        running a script.

        Returns:
            True if data file is being recorded or user clicks ok in dialog box
        """
        if self._data_file_recording:
            return True

        ret = QMessageBox.question(
            self,
            "Data file not being recorded",
            "Data is currently not being recorded. Are you sure you want to continue?",
            QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.Cancel,
        )
        return ret == QMessageBox.StandardButton.Ok

    def _run_btn_clicked(self) -> None:
        """Try to run a measure script."""
        if not self._check_data_file_recording():
            # User forgot to start data recording
            return

        file_path = self.script_path.try_get_path()
        if not file_path:
            # User cancelled
            return

        script = Script.try_load(self, file_path)
        if not script:
            # Failed to load script
            return

        # Save to settings
        settings.setValue("script/run_path", str(file_path))

        # Run the script!
        script.run(self)

    def _show_run_dialog(self, script_runner: ScriptRunner) -> None:
        """Create a new ScriptRunDialog and show it."""
        self.run_dialog = ScriptRunDialog(script_runner)
        self.run_dialog.show()

    def _hide_run_dialog(self) -> None:
        """Hide and destroy the ScriptRunDialog."""
        self.run_dialog.hide()
        del self.run_dialog

    def _set_spectrometer_ready(self, ready: bool) -> None:
        if ready == self._spectrometer_ready:
            # The ready state hasn't changed
            return

        self._spectrometer_ready = ready

        if ready:
            self._enable_counter.increment()
        else:
            self._enable_counter.decrement()

    def _on_spectrometer_status_changed(self, status: SpectrometerStatus) -> None:
        """Change the enable counter when the spectrometer's status changes."""
        self._set_spectrometer_ready(status == SpectrometerStatus.CONNECTED)

    def _on_spectrometer_disconnect(self, instance: DeviceInstanceRef) -> None:
        """Decrement the enable counter when the spectrometer disconnects."""
        self._set_spectrometer_ready(False)
