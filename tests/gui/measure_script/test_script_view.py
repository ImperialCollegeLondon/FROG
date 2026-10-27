"""Tests for ScriptControl."""

from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, Mock, call, patch

import pytest
from PySide6.QtWidgets import QMessageBox, QPushButton, QWidget
from pytestqt.qtbot import QtBot

from frog.config import DEFAULT_SCRIPT_PATH, SPECTROMETER_TOPIC
from frog.gui.measure_script.script_run_dialog import ScriptRunDialog
from frog.gui.measure_script.script_view import ScriptControl
from frog.spectrometer_status import SpectrometerStatus


@pytest.fixture
@patch("frog.gui.measure_script.script_view.get_setting_or_default")
def script_control(get_setting_or_default_mock: Mock, qtbot: QtBot) -> ScriptControl:
    """Provides a ScriptControl."""
    # NB: This will need to be changed if we load more than one setting
    get_setting_or_default_mock.return_value = "/my/path.yaml"
    return ScriptControl()


def get_button(widget: QWidget, text: str) -> QPushButton:
    """Get the button with the specified text label."""
    buttons = cast(list[QPushButton], widget.findChildren(QPushButton))
    return next(btn for btn in buttons if btn.text() == text)


def click_button(widget: QWidget, text: str) -> None:
    """Click the button with the specified text label."""
    get_button(widget, text).click()


@patch("frog.gui.measure_script.script_view.get_setting_or_default")
def test_init(
    get_setting_or_default_mock: Mock, subscribe_mock: Mock, qtbot: QtBot
) -> None:
    """Test ScriptControl's constructor."""
    get_setting_or_default_mock.return_value = "/my/path.yaml"
    script_control = ScriptControl()
    assert not script_control._spectrometer_ready
    assert not script_control._data_file_recording

    # Check we are subscribed to the relevant pubsub messages
    subscribe_mock.assert_has_calls(
        (
            call(script_control._show_run_dialog, "measure_script.begin"),
            call(script_control._hide_run_dialog, "measure_script.end"),
            call(
                script_control._on_spectrometer_status_changed,
                f"device.{SPECTROMETER_TOPIC}.status",
            ),
            call(
                script_control._on_spectrometer_disconnect,
                f"device.closed.{SPECTROMETER_TOPIC}",
            ),
            call(script_control._on_recording_start, "data_file.opened"),
            call(script_control._on_recording_stop, "data_file.close"),
        ),
        any_order=True,
    )


@patch("frog.gui.measure_script.script_view.get_setting_or_default")
@pytest.mark.parametrize("prev_path", (Path("/my/path.yaml"), ""))
def test_init_path_setting(
    get_setting_or_default_mock: Mock, prev_path: Path, qtbot: QtBot
) -> None:
    """Check that the constructor correctly loads previous path from settings."""
    get_setting_or_default_mock.return_value = str(prev_path)
    script_control = ScriptControl()

    # NB: This will need to be changed if we load more than one setting
    get_setting_or_default_mock.assert_called_once_with("script/run_path", "")

    # Check that the initial path is correct
    assert script_control.script_path.line_edit.text() == str(prev_path)


def test_on_recording_start(script_control: ScriptControl) -> None:
    """Test the _on_recording_start() method."""
    script_control._data_file_recording = False
    script_control._on_recording_start()
    assert script_control._data_file_recording


def test_on_recording_stop(script_control: ScriptControl) -> None:
    """Test the _on_recording_stop() method."""
    script_control._data_file_recording = True
    script_control._on_recording_stop()
    assert not script_control._data_file_recording


@patch("frog.gui.measure_script.script_view.ScriptEditDialog")
def test_create_button(
    edit_dialog_mock: Mock, script_control: ScriptControl, qtbot: QtBot
) -> None:
    """Test that the create button works."""
    dialog = MagicMock()
    edit_dialog_mock.return_value = dialog

    click_button(script_control, "Create new script")

    # Check that dialog was created and shown
    edit_dialog_mock.assert_called_once_with()
    assert script_control.edit_dialog is dialog
    dialog.show.assert_called_once_with()


@patch("frog.gui.measure_script.script_view.Script")
@patch("frog.gui.measure_script.script_view.QFileDialog")
@patch("frog.gui.measure_script.script_view.ScriptEditDialog")
def test_edit_button_file_dialog_closed(
    edit_dialog_mock: Mock,
    file_dialog_mock: Mock,
    script_mock: Mock,
    script_control: ScriptControl,
    qtbot: QtBot,
) -> None:
    """Test that the edit button doesn't create a new dialog if file dialog closed."""
    file_dialog_mock.getOpenFileName.return_value = ("", "*.yaml")
    click_button(script_control, "Edit script")
    edit_dialog_mock.assert_not_called()


@patch("frog.gui.measure_script.script_view.Script")
@patch("frog.gui.measure_script.script_view.QFileDialog")
@patch("frog.gui.measure_script.script_view.ScriptEditDialog")
def test_edit_button_bad_script(
    edit_dialog_mock: Mock,
    file_dialog_mock: Mock,
    script_mock: Mock,
    script_control: ScriptControl,
    qtbot: QtBot,
) -> None:
    """Test that the edit button behaves correctly when script fails to load."""
    file_dialog_mock.getOpenFileName.return_value = ("/my/path.yaml", "*.yaml")
    script_mock.try_load.return_value = None  # Indicates error

    click_button(script_control, "Edit script")
    edit_dialog_mock.assert_not_called()


@patch("frog.gui.measure_script.script_view.Script")
@patch("frog.gui.measure_script.script_view.QFileDialog")
@patch("frog.gui.measure_script.script_view.ScriptEditDialog")
def test_edit_button_success(
    edit_dialog_mock: Mock,
    file_dialog_mock: Mock,
    script_mock: Mock,
    script_control: ScriptControl,
    qtbot: QtBot,
) -> None:
    """Test that the edit button creates a new dialog when no error occurs."""
    dialog = MagicMock()
    edit_dialog_mock.return_value = dialog
    file_dialog_mock.getOpenFileName.return_value = ("/my/path.yaml", "*.yaml")
    script = MagicMock()
    script_mock.try_load.return_value = script

    click_button(script_control, "Edit script")

    # Check that a file dialog is opened with the correct parameters
    file_dialog_mock.getOpenFileName.assert_called_once_with(
        script_control,
        caption="Choose script file to edit",
        dir=str(DEFAULT_SCRIPT_PATH),
        filter="*.yaml",
    )

    # Check that a script is loaded from the correct path
    script_mock.try_load.assert_called_once_with(script_control, Path("/my/path.yaml"))

    # Check that dialog is created and shown
    edit_dialog_mock.assert_called_once_with(script)
    assert script_control.edit_dialog is dialog
    dialog.show.assert_called_once_with()


def test_check_data_file_already_recording(script_control: ScriptControl) -> None:
    """Test the _check_data_file_recording() method when recording is happening."""
    script_control._data_file_recording = True
    assert script_control._check_data_file_recording()


@pytest.mark.parametrize(
    "button,output",
    ((QMessageBox.StandardButton.Ok, True), (QMessageBox.StandardButton.Cancel, False)),
)
@patch.object(QMessageBox, "question")
def test_check_data_file_not_recording(
    question_mock: Mock,
    button: QMessageBox.StandardButton,
    output: bool,
    script_control: ScriptControl,
) -> None:
    """Test the _check_data_file_recording() method when not recording."""
    script_control._data_file_recording = False
    question_mock.return_value = button
    assert script_control._check_data_file_recording() == output


def _run_script(script_control: ScriptControl) -> None:
    """Click the run button in the ScriptControl.

    The button will be disabled as no devices are connected, so we have to enable it
    before we can click it.
    """
    btn = get_button(script_control, "Run script")
    btn.setEnabled(True)
    btn.click()


@patch("frog.gui.measure_script.script_view.set_setting")
@patch("frog.gui.measure_script.script_view.Script")
def test_run_button_recording_check_failed(
    script_mock: Mock,
    set_setting_mock: Mock,
    script_control: ScriptControl,
    qtbot: QtBot,
) -> None:
    """Test that the run button does nothing if the data file recording check fails."""
    with patch.object(
        script_control, "_check_data_file_recording"
    ) as check_recording_mock:
        check_recording_mock.return_value = False
        _run_script(script_control)

        # Check that function returns without loading script
        script_mock.try_load.assert_not_called()

        # Check that settings weren't updated
        set_setting_mock.assert_not_called()


@patch("frog.gui.measure_script.script_view.set_setting")
@patch("frog.gui.measure_script.script_view.Script")
def test_run_button_no_file_path(
    script_mock: Mock,
    set_setting_mock: Mock,
    script_control: ScriptControl,
    qtbot: QtBot,
) -> None:
    """Test that the run button does nothing if no path selected."""
    with patch.object(
        script_control, "_check_data_file_recording"
    ) as check_recording_mock:
        check_recording_mock.return_value = True
        with patch.object(
            script_control.script_path, "try_get_path"
        ) as try_get_path_mock:
            try_get_path_mock.return_value = None
            _run_script(script_control)

            # Check that function returns without loading script
            script_mock.try_load.assert_not_called()

            # Check that settings weren't updated
            set_setting_mock.assert_not_called()


@patch("frog.gui.measure_script.script_view.set_setting")
@patch("frog.gui.measure_script.script_view.Script")
def test_run_button_bad_script(
    script_mock: Mock,
    set_setting_mock: Mock,
    script_control: ScriptControl,
    qtbot: QtBot,
) -> None:
    """Test that the run button does nothing if script fails to load."""
    with patch.object(
        script_control, "_check_data_file_recording"
    ) as check_recording_mock:
        check_recording_mock.return_value = True
        script_mock.try_load.return_value = None
        _run_script(script_control)

        # Check that settings weren't updated
        set_setting_mock.assert_not_called()


@patch("frog.gui.measure_script.script_view.set_setting")
@patch("frog.gui.measure_script.script_view.Script")
def test_run_button_success(
    script_mock: Mock,
    set_setting_mock: Mock,
    script_control: ScriptControl,
    qtbot: QtBot,
) -> None:
    """Test that the run button works if no error occurs."""
    with patch.object(
        script_control, "_check_data_file_recording"
    ) as check_recording_mock:
        check_recording_mock.return_value = True
        with patch.object(
            script_control.script_path, "try_get_path"
        ) as try_get_path_mock:
            script_path = Path("/my/path.yaml")
            try_get_path_mock.return_value = script_path
            script = MagicMock()
            script_mock.try_load.return_value = script

            _run_script(script_control)

            # Check that settings were updated
            set_setting_mock.assert_any_call("script/run_path", str(script_path))

            # Check that the script was started
            script.run.assert_called_once_with(script_control)


@patch("frog.gui.measure_script.script_view.ScriptRunDialog")
def test_show_run_dialog(
    run_dialog_mock: Mock,
    script_control: ScriptControl,
    qtbot: QtBot,
) -> None:
    """Test the _show_run_dialog() method."""
    dialog = MagicMock()
    run_dialog_mock.return_value = dialog

    runner = MagicMock()
    script_control._show_run_dialog(runner)

    # Check that the dialog was created and shown
    run_dialog_mock.assert_called_once_with(runner)
    assert script_control.run_dialog is dialog
    dialog.show.assert_called_once_with()


def test_hide_run_dialog(
    script_control: ScriptControl,
    run_dialog: ScriptRunDialog,
    sendmsg_mock: MagicMock,
    qtbot: QtBot,
) -> None:
    """Test the _hide_run_dialog() method."""
    dialog = MagicMock()
    script_control.run_dialog = dialog
    script_control._hide_run_dialog()

    dialog.hide.assert_called_once_with()  # Check window is hidden
    assert not hasattr(script_control, "run_dialog")  # Check attribute is deleted


def test_hide_run_dialog_no_abort(
    script_control: ScriptControl,
    run_dialog: ScriptRunDialog,
    sendmsg_mock: MagicMock,
    qtbot: QtBot,
) -> None:
    """Test the _hide_run_dialog() method doesn't abort the measure script.

    This method should only be run when the measure script completes successfully.
    """
    script_control.run_dialog = run_dialog
    script_control._hide_run_dialog()

    # Check that measure_script.abort message isn't sent
    sendmsg_mock.assert_not_called()


@pytest.mark.parametrize("old_ready_state", (True, False))
def test_set_spectrometer_ready(
    old_ready_state: bool, script_control: ScriptControl, qtbot: QtBot
) -> None:
    """Test the _set_spectrometer_ready() method when the status becomes ready."""
    script_control._spectrometer_ready = old_ready_state

    with patch.object(script_control, "_enable_counter") as counter_mock:
        script_control._set_spectrometer_ready(True)
        if old_ready_state:
            counter_mock.increment.assert_not_called()
        else:
            counter_mock.increment.assert_called_once_with()

        assert script_control._spectrometer_ready


@pytest.mark.parametrize("old_ready_state", (True, False))
def test_set_spectrometer_not_ready(
    old_ready_state: bool, script_control: ScriptControl, qtbot: QtBot
) -> None:
    """Test the _set_spectrometer_ready() method when the status becomes not ready."""
    script_control._spectrometer_ready = old_ready_state

    with patch.object(script_control, "_enable_counter") as counter_mock:
        script_control._set_spectrometer_ready(False)
        if not old_ready_state:
            counter_mock.decrement.assert_not_called()
        else:
            counter_mock.decrement.assert_called_once_with()

        assert not script_control._spectrometer_ready


def test_on_spectrometer_status_changed_ready(
    script_control: ScriptControl, qtbot: QtBot
) -> None:
    """Test the _on_spectrometer_status_changed() method when it becomes ready."""
    with patch.object(script_control, "_set_spectrometer_ready") as ready_mock:
        script_control._on_spectrometer_status_changed(SpectrometerStatus.CONNECTED)
        ready_mock.assert_called_once_with(True)


@pytest.mark.parametrize(
    "status",
    (status for status in SpectrometerStatus if status != SpectrometerStatus.CONNECTED),
)
def test_on_spectrometer_status_changed_not_ready(
    status: SpectrometerStatus, script_control: ScriptControl, qtbot: QtBot
) -> None:
    """Test the _on_spectrometer_status_changed() method when it becomes not ready."""
    with patch.object(script_control, "_set_spectrometer_ready") as ready_mock:
        script_control._on_spectrometer_status_changed(status)
        ready_mock.assert_called_once_with(False)


def test_on_spectrometer_disconnect(
    script_control: ScriptControl, qtbot: QtBot
) -> None:
    """Test the _on_spectrometer_disconnect() method."""
    with patch.object(script_control, "_set_spectrometer_ready") as ready_mock:
        script_control._on_spectrometer_disconnect(MagicMock())
        ready_mock.assert_called_once_with(False)
