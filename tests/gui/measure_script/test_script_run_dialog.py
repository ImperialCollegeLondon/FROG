"""Tests for ScriptRunDialog."""

from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, Mock, patch

import pytest
from PySide6.QtWidgets import QDialogButtonBox, QProgressBar
from pytestqt.qtbot import QtBot

from frog.gui.measure_script.script import Measurement, Script, ScriptRunner
from frog.gui.measure_script.script_run_dialog import (
    ScriptRunDialog,
    get_total_steps,
)


@pytest.mark.parametrize("repeats", range(1, 4))
def test_get_total_steps_single(repeats: int) -> None:
    """Test the get_total_steps() function for a single measurement."""
    script = Script(Path(), 1, ({"angle": 90, "measurements": repeats},))
    assert get_total_steps(script) == 1 + repeats


_MEASUREMENTS = range(1, 4)


@pytest.mark.parametrize("measurements_count", range(1, len(_MEASUREMENTS)))
def test_get_total_steps_multi(measurements_count: int) -> None:
    """Test the get_total_steps() function for multiple measurements."""
    measurements = [
        {"angle": 90, "measurements": m} for m in _MEASUREMENTS[:measurements_count]
    ]
    script = Script(Path(), 1, measurements)
    assert get_total_steps(script) == measurements_count + sum(
        _MEASUREMENTS[:measurements_count]
    )


@pytest.mark.parametrize("repeats", range(1, 4))
def test_get_total_steps_with_repeats(repeats: int) -> None:
    """Test the get_total_steps() function works with multiple repeats."""
    measurements = [{"angle": 90, "measurements": m} for m in _MEASUREMENTS]
    script = Script(Path(), repeats, measurements)
    assert get_total_steps(script) == repeats * (
        len(_MEASUREMENTS) + sum(_MEASUREMENTS)
    )


@patch("frog.gui.measure_script.script_run_dialog.get_total_steps")
@patch("frog.gui.measure_script.script_run_dialog.QProgressBar")
def test_init(
    progress_bar_mock: Mock,
    get_total_steps_mock: Mock,
    runner: ScriptRunner,
    subscribe_mock: MagicMock,
    sendmsg_mock: MagicMock,
    qtbot: QtBot,
) -> None:
    """Test ScriptRunDialog's constructor."""
    get_total_steps_mock.return_value = "MAGIC"
    progress_bar = QProgressBar()
    progress_bar_mock.return_value = progress_bar
    with patch.object(progress_bar, "setMaximum") as set_max_mock:
        dialog = ScriptRunDialog(runner)

        # Check that the progress bar's maximum is set to max number of steps
        get_total_steps_mock.assert_called_once_with(runner.script)
        set_max_mock.assert_called_once_with("MAGIC")

        # Check that we're subscribed to the relevant measure script messages
        subscribe_mock.assert_any_call(
            dialog._on_start_moving, "measure_script.start_moving"
        )
        subscribe_mock.assert_any_call(
            dialog._on_start_measuring, "measure_script.start_measuring"
        )


def test_cancel_button(
    run_dialog: ScriptRunDialog, sendmsg_mock: MagicMock, qtbot: QtBot
) -> None:
    """Check that clicking the cancel button aborts the measure script."""
    buttonbox = cast(QDialogButtonBox, run_dialog.findChild(QDialogButtonBox))
    buttonbox.button(QDialogButtonBox.StandardButton.Cancel).click()
    run_dialog._stop_dlg.accept()
    sendmsg_mock.assert_any_call("measure_script.abort")


def test_close(
    run_dialog: ScriptRunDialog, sendmsg_mock: MagicMock, qtbot: QtBot
) -> None:
    """Check that closing the dialog aborts the measure script."""
    run_dialog.close()
    run_dialog._stop_dlg.accept()
    sendmsg_mock.assert_any_call("measure_script.abort")


def test_update(
    run_dialog: ScriptRunDialog, runner: ScriptRunner, qtbot: QtBot
) -> None:
    """Test the _update() method."""
    with patch.object(run_dialog, "_progress_bar") as progress_bar_mock:
        progress_bar_mock.value.return_value = 1
        with patch.object(run_dialog, "_label") as label_mock:
            run_dialog._update(runner, "hello")

            # Check progress bar is incremented by one
            progress_bar_mock.value.assert_called_once_with()
            progress_bar_mock.setValue.assert_called_once_with(2)

            # Check label is updated
            label_mock.setText.assert_called_once_with(
                f"Repeat {runner.measurement_iter.current_repeat + 1}"
                f" of {runner.script.repeats}: hello"
            )


@pytest.mark.parametrize("angle,angle_str", ((90.0, "90.0°"), ["zenith"] * 2))
def test_on_start_moving(
    angle: float | str,
    angle_str: str,
    run_dialog: ScriptRunDialog,
    runner_measuring: ScriptRunner,
    qtbot: QtBot,
) -> None:
    """Test the dialog is updated correctly when moving starts."""
    with patch.object(run_dialog, "_update") as update_mock:
        runner_measuring.current_measurement = Measurement(angle, 1)
        run_dialog._on_start_moving(runner_measuring)
        update_mock.assert_called_once_with(runner_measuring, f"Moving to {angle_str}")


def test_on_start_measuring(
    run_dialog: ScriptRunDialog, runner_measuring: ScriptRunner, qtbot: QtBot
) -> None:
    """Test the dialog is updated correctly when measuring starts."""
    with patch.object(run_dialog, "_update") as update_mock:
        run_dialog._on_start_measuring(runner_measuring)
        update_mock.assert_called_once_with(
            runner_measuring,
            f"Carrying out measurement {runner_measuring.current_measurement_count + 1}"
            f" of {runner_measuring.current_measurement.measurements}",
        )


def test_toggle_paused(
    run_dialog: ScriptRunDialog,
    runner: ScriptRunner,
    sendmsg_mock: MagicMock,
    qtbot: QtBot,
) -> None:
    """Test the widgets update correctly when paused/unpaused."""
    with patch.object(run_dialog, "_progress_bar") as progress_bar_mock:
        with patch.object(run_dialog, "_pause_btn") as pause_btn_mock:
            pause_btn_mock.text.return_value = "Pause"  # Start off in unpaused state
            # Pause
            run_dialog._toggle_paused()

            # Check "pause" broadcast
            sendmsg_mock.assert_any_call("measure_script.pause")

            # Check progress bar string format is updated to display "PAUSED"
            progress_bar_mock.setFormat.assert_called_with("PAUSED (%p%)")

            # Check pause button text is updated
            pause_btn_mock.setText.assert_called_once_with("Unpause")

            pause_btn_mock.text.return_value = "Unpause"  # Now in paused state
            # Unpause
            run_dialog._toggle_paused()

            # Check "unpause" broadcast
            sendmsg_mock.assert_any_call("measure_script.unpause")

            # Check progress bar string format is reverted to display percentage
            progress_bar_mock.setFormat.assert_called_with("%p%")

            # Check pause button text is updated
            pause_btn_mock.setText.assert_called_with("Pause")
