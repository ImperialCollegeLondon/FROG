"""Tests for the ScriptRunner class."""

from itertools import chain
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

import pytest
from statemachine import State

from frog.config import SPECTROMETER_TOPIC, STEPPER_MOTOR_TOPIC
from frog.device_info import DeviceInstanceRef
from frog.gui.measure_script.script import Script, ScriptRunner
from frog.spectrometer_status import SpectrometerStatus


def test_init(subscribe_mock: MagicMock) -> None:
    """Test ScriptRunner's constructor."""
    script = Script(Path(), 1, ())
    runner = ScriptRunner(script)

    # Check we're subscribed to abort messages
    subscribe_mock.assert_has_calls(
        (
            call(runner.abort, "measure_script.abort"),
            call(runner.pause, "measure_script.pause"),
            call(runner.unpause, "measure_script.unpause"),
        ),
        any_order=True,
    )

    # Initial state
    assert runner.current_state == ScriptRunner.not_running

    # Should start unpaused
    assert not runner.paused


def test_start_moving(
    runner: ScriptRunner, subscribe_mock: MagicMock, sendmsg_mock: MagicMock
) -> None:
    """Test the start_moving() method."""
    runner.start_moving()
    assert runner.current_state == ScriptRunner.moving

    # Check that new measurement was loaded correctly
    assert runner.current_measurement is runner.script.sequence[0]
    assert runner.current_measurement_count == 0

    # Check that we have signalled start of script and that command has been sent to
    # stepper motor
    sendmsg_mock.assert_has_calls(
        (
            call("measure_script.begin", script_runner=runner),
            call("measure_script.start_moving", script_runner=runner),
            call(
                f"device.{STEPPER_MOTOR_TOPIC}.move.begin",
                target=runner.script.sequence[0].angle,
            ),
        )
    )

    # Check subscriptions
    subscribe_mock.assert_has_calls(
        (
            call(runner.finish_moving, f"device.{STEPPER_MOTOR_TOPIC}.move.end"),
            call(runner._on_stepper_motor_error, f"device.error.{STEPPER_MOTOR_TOPIC}"),
            call(runner._on_spectrometer_error, f"device.error.{SPECTROMETER_TOPIC}"),
        ),
        any_order=True,
    )


@pytest.mark.parametrize("repeats", range(1, 3))
def test_finish_moving(
    repeats: int,
    subscribe_mock: MagicMock,
    unsubscribe_mock: MagicMock,
    sendmsg_mock: MagicMock,
):
    """Test that the ScriptRunner terminates after n repeats."""
    script = Script(Path(), repeats, ({"angle": 0.0, "measurements": 1},))
    script_runner = ScriptRunner(script)
    assert script_runner.current_state == ScriptRunner.not_running

    script_runner.start_moving()
    for _ in range(repeats):
        assert script_runner.current_state == ScriptRunner.moving
        script_runner.finish_moving()
        assert script_runner.current_state == ScriptRunner.waiting_to_measure
        script_runner.start_measuring()

        sendmsg_mock.reset_mock()
        script_runner.start_next_move()

    assert script_runner.current_state == ScriptRunner.not_running

    # Check we've unsubscribed from device messages
    unsubscribe_mock.assert_has_calls(
        (
            call(script_runner.finish_moving, f"device.{STEPPER_MOTOR_TOPIC}.move.end"),
            call(
                script_runner._on_stepper_motor_error,
                f"device.error.{STEPPER_MOTOR_TOPIC}",
            ),
            call(
                script_runner._on_spectrometer_error,
                f"device.error.{SPECTROMETER_TOPIC}",
            ),
        ),
        any_order=True,
    )

    # Check that this message is sent on the last iteration
    sendmsg_mock.assert_called_once_with("measure_script.end")


def test_finish_moving_paused(
    runner: ScriptRunner,
    subscribe_mock: MagicMock,
    unsubscribe_mock: MagicMock,
    sendmsg_mock: MagicMock,
) -> None:
    """Test that finish_moving() waits if paused."""
    runner.current_state = ScriptRunner.moving
    runner.pause()
    runner.finish_moving()
    assert runner.current_state == ScriptRunner.waiting_to_measure


def test_start_measuring(
    runner: ScriptRunner,
    subscribe_mock: MagicMock,
    unsubscribe_mock: MagicMock,
    sendmsg_mock: MagicMock,
) -> None:
    """Test the start_measuring() method."""
    runner.current_state = ScriptRunner.moving
    runner.finish_moving()
    assert runner.current_state == ScriptRunner.waiting_to_measure
    runner.start_measuring()
    assert runner.current_state == ScriptRunner.measuring

    sendmsg_mock.assert_any_call(f"device.{SPECTROMETER_TOPIC}.start_measuring")
    sendmsg_mock.assert_any_call("measure_script.start_measuring", script_runner=runner)


def test_repeat_measuring(
    runner_measuring: ScriptRunner,
    subscribe_mock: MagicMock,
    unsubscribe_mock: MagicMock,
    sendmsg_mock: MagicMock,
) -> None:
    """Test that repeat measurements work correctly."""
    with patch.object(runner_measuring, "_request_measurement") as request_mock:
        runner_measuring.repeat_measuring()
        assert runner_measuring.current_state == ScriptRunner.waiting_to_measure
        request_mock.assert_called_once_with()


def test_repeat_measuring_paused(runner_measuring: ScriptRunner) -> None:
    """Test that repeat_measuring() waits if paused."""
    with patch.object(runner_measuring, "_request_measurement") as request_mock:
        runner_measuring.pause()
        runner_measuring.repeat_measuring()
        assert runner_measuring.current_state == ScriptRunner.waiting_to_measure
        request_mock.assert_not_called()


def test_cancel_measuring(
    runner_measuring: ScriptRunner, unsubscribe_mock: MagicMock
) -> None:
    """Test the cancel_measuring() method."""
    runner_measuring.cancel_measuring()
    assert runner_measuring.current_state == ScriptRunner.not_running


def test_measuring_started_success(
    runner: ScriptRunner,
    subscribe_mock: MagicMock,
    unsubscribe_mock: MagicMock,
    sendmsg_mock: MagicMock,
) -> None:
    """Test that polling starts when measurement has started successfully."""
    runner.current_state = ScriptRunner.waiting_to_measure
    runner._measuring_start(SpectrometerStatus.IDLE)
    unsubscribe_mock.assert_called_with(
        runner._measuring_start, f"device.{SPECTROMETER_TOPIC}.status.measuring"
    )
    subscribe_mock.assert_called_with(
        runner._measuring_end, f"device.{SPECTROMETER_TOPIC}.status.connected"
    )


def test_on_exit_measuring(
    runner_measuring: ScriptRunner, unsubscribe_mock: MagicMock
) -> None:
    """Test that the timer is stopped when exiting measuring state."""
    runner_measuring.on_exit_measuring()
    unsubscribe_mock.assert_called_once_with(
        runner_measuring._measuring_end, f"device.{SPECTROMETER_TOPIC}.status.connected"
    )


@pytest.mark.parametrize("current_measurement_repeat", range(3))
def test_measuring_end(
    current_measurement_repeat: int, runner_measuring: ScriptRunner
) -> None:
    """Test that _measuring_end() works correctly.

    It should trigger a repeat measurement if there are more to do and otherwise move
    onto the next measurement.
    """
    runner_measuring.current_measurement_count = current_measurement_repeat

    with patch.object(runner_measuring, "start_next_move") as start_next_move_mock:
        with patch.object(
            runner_measuring, "repeat_measuring"
        ) as repeat_measuring_mock:
            runner_measuring._measuring_end(SpectrometerStatus.CONNECTED)

            assert (
                runner_measuring.current_measurement_count
                == current_measurement_repeat + 1
            )
            if (
                runner_measuring.current_measurement_count
                == runner_measuring.current_measurement.measurements
            ):
                start_next_move_mock.assert_called_once()
                repeat_measuring_mock.assert_not_called()
            else:
                start_next_move_mock.assert_not_called()
                repeat_measuring_mock.assert_called_once()


def test_start_next_move_paused(runner_measuring: ScriptRunner) -> None:
    """Test that start_next_move() waits if paused."""
    runner_measuring.pause()
    runner_measuring.start_next_move()
    assert runner_measuring.current_state == ScriptRunner.waiting_to_move


@pytest.mark.parametrize("state", ScriptRunner.states)
def test_abort(
    state: State,
    runner: ScriptRunner,
    subscribe_mock: Mock,
    unsubscribe_mock: Mock,
    sendmsg_mock: Mock,
) -> None:
    """Test that the abort() method resets the ScriptRunner's state to not_running."""
    runner.current_state = state
    runner.abort()
    assert runner.current_state == ScriptRunner.not_running


def test_on_stepper_motor_error(runner: ScriptRunner) -> None:
    """Test that the _on_stepper_motor_error() method calls abort()."""
    with patch.object(runner, "abort") as abort_mock:
        runner._on_stepper_motor_error(
            instance=DeviceInstanceRef(STEPPER_MOTOR_TOPIC), error=RuntimeError("hello")
        )
        abort_mock.assert_called_once_with()


@patch("frog.gui.measure_script.script.show_error_message")
def test_on_spectrometer_error(
    show_error_message_mock: Mock, runner: ScriptRunner
) -> None:
    """Test the _on_spectrometer_error() method."""
    with patch.object(runner, "abort") as abort_mock:
        runner._on_spectrometer_error(
            instance=DeviceInstanceRef(SPECTROMETER_TOPIC),
            error=RuntimeError("ERROR MESSAGE"),
        )
        abort_mock.assert_called_once_with()
        show_error_message_mock.assert_called_once()


def test_pause(runner: ScriptRunner) -> None:
    """Test the pause() method."""
    runner.pause()
    assert runner.paused


@pytest.mark.parametrize(
    "begin_state,end_state",
    chain(
        (
            (val, val)
            for val in (
                ScriptRunner.not_running,
                ScriptRunner.moving,
                ScriptRunner.measuring,
                ScriptRunner.waiting_to_measure,
            )
        ),
        ((ScriptRunner.waiting_to_move, ScriptRunner.moving),),
    ),
)
def test_unpause(begin_state: State, end_state: State, runner: ScriptRunner) -> None:
    """Test the unpause() method.

    For the special states waiting_to_move and waiting_to_measure, unpausing the script
    should trigger a transition to moving and measuring, respectively.
    """
    runner.current_state = begin_state
    runner.pause()
    runner.unpause()
    assert not runner.paused
    assert runner.current_state == end_state


def test_unpause_waiting_to_measure(runner: ScriptRunner) -> None:
    """Test that unpausing while waiting to measure triggers a measurement request."""
    with patch.object(runner, "_request_measurement") as request_mock:
        runner.pause()
        runner.current_state = ScriptRunner.waiting_to_measure
        request_mock.assert_not_called()
        runner.unpause()
        request_mock.assert_called_once_with()
