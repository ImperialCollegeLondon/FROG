"""Tests for DummyOPUSInterface."""

from unittest.mock import MagicMock, Mock, patch

import pytest
from statemachine import State
from statemachine.exceptions import TransitionNotAllowed

from frog.hardware.plugins.spectrometer.dummy_opus_interface import (
    DummyOPUSInterface,
    OPUSError,
    OPUSErrorInfo,
    OPUSStateMachine,
)


@pytest.fixture
@patch("frog.hardware.plugins.spectrometer.dummy_opus_interface.OPUSStateMachine")
def opus(sm_mock: Mock) -> DummyOPUSInterface:
    """A fixture for DummyOPUSInterface."""
    sm_mock.return_value = MagicMock()

    with patch.object(DummyOPUSInterface, "on_enter_state"):
        opus = DummyOPUSInterface()
        opus.send_status_message = MagicMock()  # type: ignore[method-assign]
        return opus


@pytest.fixture
@patch("frog.hardware.plugins.spectrometer.dummy_opus_interface.QTimer")
def sm(timer_mock: Mock) -> OPUSStateMachine:
    """A fixture for OPUSStateMachine."""
    timer_mock.return_value = MagicMock()
    return OPUSStateMachine(1.0)


class _MockObserver:
    """A state machine observer which tracks state changes."""

    def __init__(self) -> None:
        self._states: list[State] = []

    def on_enter_state(self, target: State) -> None:
        self._states.append(target)

    def assert_has_states(self, *states: State) -> None:
        assert states == tuple(self._states)


@pytest.mark.parametrize("duration_secs,duration_ms", ((0.5, 500), (1.0, 1000)))
@patch("frog.hardware.plugins.spectrometer.dummy_opus_interface.QTimer")
def test_sm_init(
    timer_mock: Mock, duration_secs: float, duration_ms: int, qtbot
) -> None:
    """Test the state machine's constructor."""
    timer = MagicMock()
    timer_mock.return_value = timer

    sm = OPUSStateMachine(duration_secs)
    timer.setInterval.assert_called_once_with(duration_ms)
    timer.setSingleShot.assert_called_once_with(True)
    timer.timeout.connect.assert_called_once_with(sm._on_measure_finished)


def test_sm_connect(sm: OPUSStateMachine) -> None:
    """Test the connect() method."""
    assert sm.current_state == OPUSStateMachine.idle
    observer = _MockObserver()
    sm.add_observer(observer)
    sm.connect()
    observer.assert_has_states(OPUSStateMachine.connecting, OPUSStateMachine.connected)


def test_sm_start(sm: OPUSStateMachine) -> None:
    """Test the start() method."""
    with patch.object(sm, "measure_timer") as timer_mock:
        sm.current_state = OPUSStateMachine.connected
        observer = _MockObserver()
        sm.add_observer(observer)
        sm.start()
        observer.assert_has_states(OPUSStateMachine.measuring)
        timer_mock.start.assert_called_once_with()


def test_sm_stop(sm: OPUSStateMachine) -> None:
    """Test the stop() method."""
    with patch.object(sm, "measure_timer") as timer_mock:
        sm.current_state = OPUSStateMachine.measuring
        observer = _MockObserver()
        sm.add_observer(observer)
        sm.cancel()
        observer.assert_has_states(
            OPUSStateMachine.cancelling, OPUSStateMachine.connected
        )
        timer_mock.stop.assert_called_once_with()


@patch("frog.hardware.plugins.spectrometer.dummy_opus_interface.OPUSStateMachine")
def test_init(sm_mock: Mock) -> None:
    """Test the constructor."""
    sm = MagicMock()
    sm_mock.return_value = sm

    with patch.object(DummyOPUSInterface, "on_enter_state") as state_mock:
        opus = DummyOPUSInterface(1.0)
        assert opus.state_machine is sm
        sm_mock.assert_called_once_with(1.0)
        sm.add_observer.assert_called_once_with(opus)
        state_mock.assert_called_once_with(sm.current_state)


def test_close(opus: DummyOPUSInterface) -> None:
    """Test the close() method."""
    with patch.object(opus, "state_machine") as sm_mock:
        opus.close()
        sm_mock.measure_timer.stop.assert_called_once_with()


@pytest.mark.parametrize("command", ("connect", "start", "stop", "cancel"))
def test_run_command_success(command: str, opus: DummyOPUSInterface) -> None:
    """Test the _run_command() method."""
    with patch.object(opus, "state_machine") as sm_mock:
        opus._run_command(command)
        getattr(sm_mock, command).assert_called_once_with()


_COMMAND_ERRORS = {
    "cancel": OPUSErrorInfo.NOT_RUNNING,
    "stop": OPUSErrorInfo.NOT_RUNNING_OR_FINISHING,
    "start": OPUSErrorInfo.NOT_CONNECTED,
    "connect": OPUSErrorInfo.NOT_IDLE,
}
"""The error thrown by each command when in an invalid state."""

_COMMANDS = _COMMAND_ERRORS.keys()


@pytest.mark.parametrize("command", _COMMANDS)
def test_run_command_fail(command: str, opus: DummyOPUSInterface) -> None:
    """Test the _run_command() when an error occurs."""
    with patch.object(opus, "state_machine") as sm_mock:
        getattr(sm_mock, command).side_effect = TransitionNotAllowed(
            MagicMock(), MagicMock()
        )
        with pytest.raises(OPUSError):
            opus._run_command(command)


@pytest.mark.parametrize("command", _COMMANDS)
def test_request_command_success(command: str, opus: DummyOPUSInterface) -> None:
    """Test the request_command() method when the command succeeds."""
    with patch.object(opus, "_run_command") as run_mock:
        opus.request_command(command)
        run_mock.assert_called_once_with(command)


def test_request_command_fail(opus: DummyOPUSInterface) -> None:
    """Test the request_command() method when the command fails."""
    with patch.object(opus, "_run_command") as run_mock:
        run_mock.side_effect = OPUSError
        with pytest.raises(OPUSError):
            opus.request_command("start")
    run_mock.assert_called_once_with("start")


def test_request_command_non_existent(opus: DummyOPUSInterface) -> None:
    """Test that request_command() raises an error for an invalid command."""
    with pytest.raises(OPUSError):
        opus.request_command("non_existent")


@pytest.mark.parametrize("state", OPUSStateMachine.states)
def test_on_enter_state(state: State, opus: DummyOPUSInterface) -> None:
    """Test that state changes are broadcast."""
    opus.on_enter_state(state)
    opus.send_status_message.assert_called_once_with(state.value)  # type: ignore
