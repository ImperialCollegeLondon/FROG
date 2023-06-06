"""Tests for the ScriptRunner class."""
from itertools import chain
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, Mock, call, patch

import pytest
from statemachine import State

from finesse.config import STEPPER_MOTOR_TOPIC
from finesse.em27_status import EM27Status
from finesse.gui.measure_script.script import Script, ScriptRunner, _poll_em27_status


@patch("finesse.gui.measure_script.script.QTimer")
def test_init(
    timer_mock: Mock, subscribe_mock: MagicMock, sendmsg_mock: MagicMock
) -> None:
    """Test ScriptRunner's constructor."""
    timer = MagicMock()
    timer_mock.return_value = timer

    script = Script(Path(), 1, ())
    script_runner = ScriptRunner(script)

    # Check the constructor was called once. Will need to be amended if we add timers.
    timer_mock.assert_called_once()

    # Check timer is properly set up
    timer.setSingleShot(True)
    timer.setInterval.assert_called_once_with(1000)
    timer.timeout.connect.assert_called_once_with(_poll_em27_status)

    # Check we're stopping the motor
    sendmsg_mock.assert_any_call(f"serial.{STEPPER_MOTOR_TOPIC}.stop")

    # Check we're subscribed to abort messages
    subscribe_mock.assert_any_call(script_runner.abort, "measure_script.abort")

    # Initial state
    assert script_runner.current_state == ScriptRunner.not_running

    # Should start unpaused
    assert not script_runner.paused


def test_poll_em27_status(sendmsg_mock: Mock) -> None:
    """Test the _poll_em27_status function."""
    _poll_em27_status()
    sendmsg_mock.assert_called_once_with("opus.request", command="status")


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
    calls = (
        call("measure_script.begin", script_runner=runner),
        call("measure_script.start_moving", script_runner=runner),
        call(
            f"serial.{STEPPER_MOTOR_TOPIC}.move.begin",
            target=runner.script.sequence[0].angle,
        ),
        call(f"serial.{STEPPER_MOTOR_TOPIC}.notify_on_stopped"),
    )
    sendmsg_mock.assert_has_calls(calls)

    # Check subscriptions
    subscribe_mock.assert_any_call(
        runner.start_measuring, f"serial.{STEPPER_MOTOR_TOPIC}.move.end"
    )
    subscribe_mock.assert_any_call(
        runner._on_stepper_motor_error, f"serial.{STEPPER_MOTOR_TOPIC}.error"
    )
    subscribe_mock.assert_any_call(runner._measuring_error, "opus.error")
    subscribe_mock.assert_any_call(runner._measuring_started, "opus.response.start")
    subscribe_mock.assert_any_call(runner._status_received, "opus.response.status")


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
        script_runner.start_measuring()
        assert script_runner.current_state == ScriptRunner.measuring

        sendmsg_mock.reset_mock()
        script_runner.start_next_move()

    assert script_runner.current_state == ScriptRunner.not_running

    # Check we've unsubscribed from device messages
    unsubscribe_mock.assert_any_call(
        script_runner.start_measuring, f"serial.{STEPPER_MOTOR_TOPIC}.move.end"
    )
    unsubscribe_mock.assert_any_call(
        script_runner._on_stepper_motor_error, f"serial.{STEPPER_MOTOR_TOPIC}.error"
    )
    unsubscribe_mock.assert_any_call(script_runner._measuring_error, "opus.error")
    unsubscribe_mock.assert_any_call(
        script_runner._measuring_started, "opus.response.start"
    )
    unsubscribe_mock.assert_any_call(
        script_runner._status_received, "opus.response.status"
    )

    # Check that this message is sent on the last iteration
    sendmsg_mock.assert_called_once_with("measure_script.end")


def test_start_measuring(runner: ScriptRunner, sendmsg_mock: MagicMock) -> None:
    """Test the start_measuring() method."""
    runner.current_state = ScriptRunner.moving

    runner.start_measuring()
    assert runner.current_state == ScriptRunner.measuring

    # Check that measuring has been triggered
    sendmsg_mock.assert_any_call("opus.request", command="start")

    sendmsg_mock.assert_any_call("measure_script.start_measuring", script_runner=runner)


def test_start_measuring_paused(runner: ScriptRunner) -> None:
    """Test that start_measuring() waits if paused."""
    runner.current_state = ScriptRunner.moving
    runner.pause()

    runner.start_measuring()
    assert runner.current_state == ScriptRunner.waiting_to_measure


def test_repeat_measuring(
    runner_measuring: ScriptRunner, sendmsg_mock: MagicMock
) -> None:
    """Test that repeat measurements work correctly."""
    runner_measuring.repeat_measuring()
    assert runner_measuring.current_state == ScriptRunner.measuring

    # Check that measuring has been triggered again
    sendmsg_mock.assert_any_call("opus.request", command="start")

    sendmsg_mock.assert_any_call(
        "measure_script.start_measuring", script_runner=runner_measuring
    )


def test_repeat_measuring_paused(runner_measuring: ScriptRunner) -> None:
    """Test that repeat_measuring() waits if paused."""
    runner_measuring.pause()
    runner_measuring.repeat_measuring()
    assert runner_measuring.current_state == ScriptRunner.waiting_to_measure


def test_cancel_measuring(
    runner_measuring: ScriptRunner, unsubscribe_mock: MagicMock, sendmsg_mock: MagicMock
) -> None:
    """Test the cancel_measuring() method."""
    runner_measuring.cancel_measuring()
    assert runner_measuring.current_state == ScriptRunner.not_running

    # Check that the cancel command was sent
    sendmsg_mock.assert_called_with("opus.request", command="cancel")


@patch("finesse.gui.measure_script.script._poll_em27_status")
def test_measuring_started_success(poll_em27_mock: Mock, runner: ScriptRunner) -> None:
    """Test that polling starts when measurement has started successfully."""
    runner.current_state = ScriptRunner.measuring

    # Simulate response from EM27
    runner._measuring_started(EM27Status.IDLE, "", None)

    # Check the request is sent to the EM27
    poll_em27_mock.assert_called_once()


def test_measuring_started_fail(runner: ScriptRunner) -> None:
    """Test that _on_em27_error_message is called if starting the measurement fails."""
    runner.current_state = ScriptRunner.measuring

    with patch.object(runner, "_on_em27_error_message") as em27_error_mock:
        # Simulate response from EM27
        runner._measuring_started(EM27Status.IDLE, "", (1, "ERROR MESSAGE"))

        em27_error_mock.assert_called_once_with(1, "ERROR MESSAGE")


@pytest.mark.parametrize("status", EM27Status)
def test_status_received(status: EM27Status, runner_measuring: ScriptRunner) -> None:
    """Test that polling the EM27's status works."""
    with patch.object(runner_measuring, "_measuring_end") as measuring_end_mock:
        runner_measuring._status_received(status, "", None)

        if status == EM27Status.CONNECTED:  # indicates success
            measuring_end_mock.assert_called_once()
        else:
            measuring_end_mock.assert_not_called()


def test_status_received_error(runner_measuring: ScriptRunner) -> None:
    """Test that _on_em27_error_message is called if the status indicates an error."""
    with patch.object(runner_measuring, "_on_em27_error_message") as em27_error_mock:
        runner_measuring._status_received(EM27Status.IDLE, "", (1, "ERROR MESSAGE"))
        em27_error_mock.assert_called_once_with(1, "ERROR MESSAGE")


def test_on_exit_measuring(runner_measuring: ScriptRunner) -> None:
    """Test that the timer is stopped when exiting measuring state."""
    runner_measuring.on_exit_measuring()
    timer_stop = cast(MagicMock, runner_measuring._check_status_timer.stop)
    timer_stop.assert_called_once()


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
            runner_measuring._measuring_end()

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
        runner._on_stepper_motor_error(RuntimeError("hello"))
        abort_mock.assert_called_once_with()


@patch("finesse.gui.measure_script.script.show_error_message")
def test_on_em27_error(show_error_message_mock: Mock, runner: ScriptRunner) -> None:
    """Test the _on_em27_error() method."""
    with patch.object(runner, "abort") as abort_mock:
        runner._on_em27_error("ERROR MESSAGE")
        abort_mock.assert_called_once_with()
        show_error_message_mock.assert_called_once_with(
            None,
            "EM27 error occurred. Measure script will stop running.\n\nERROR MESSAGE",
        )


def test_on_em27_error_message(runner: ScriptRunner) -> None:
    """Test the _on_em27_error_message() method."""
    with patch.object(runner, "_on_em27_error") as em27_error_mock:
        runner._on_em27_error_message(1, "ERROR MESSAGE")
        em27_error_mock.assert_called_once_with("Error 1: ERROR MESSAGE")


def test_measuring_error(runner: ScriptRunner) -> None:
    """Test the _measuring_error() method."""
    with patch.object(runner, "_on_em27_error") as em27_error_mock:
        error = RuntimeError("hello")
        runner._measuring_error(error)
        em27_error_mock.assert_called_once_with(str(error))


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
            )
        ),
        (
            (ScriptRunner.waiting_to_move, ScriptRunner.moving),
            (ScriptRunner.waiting_to_measure, ScriptRunner.measuring),
        ),
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
