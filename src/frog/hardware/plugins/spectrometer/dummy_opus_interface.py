"""Provides a dummy EM27 device for interfacing with."""

import logging
from enum import Enum
from typing import ClassVar

from PySide6.QtCore import QTimer
from statemachine import State, StateMachine
from statemachine.exceptions import TransitionNotAllowed

from frog.hardware.plugins.spectrometer.opus_interface_base import (
    OPUSError,
    OPUSInterfaceBase,
)
from frog.spectrometer_status import SpectrometerStatus


class OPUSErrorInfo(Enum):
    """Represents an error code and description for OPUS errors.

    The codes and descriptions are taken from the manual.
    """

    NO_ERROR = (0, "No error")
    NOT_IDLE = (1, "Status is not 'Idle' although required for current command")
    NOT_RUNNING = (2, "Status is not 'Running' although required for current command")
    NOT_RUNNING_OR_FINISHING = (
        3,
        "Status is not 'Running' or 'Finishing' although required for current command",
    )
    UNKNOWN_COMMAND = (4, "Unknown command")
    WEBSITE_NOT_FOUND = (5, "Website not found")
    NO_RESULT = (6, "No result available")
    NOT_CONNECTED = (7, "System not connected")

    def raise_exception(self) -> None:
        """Raise this error as an exception."""
        raise OPUSError.from_response(*self.value)


class OPUSStateMachine(StateMachine):
    """An FSM for keeping track of the internal state of the mock device."""

    idle = State("Idle", SpectrometerStatus.IDLE, initial=True)
    connecting = State("Connecting", SpectrometerStatus.CONNECTING)
    connected = State("Connected", SpectrometerStatus.CONNECTED)
    measuring = State("Measuring", SpectrometerStatus.MEASURING)
    finishing = State("Finishing current measurement", SpectrometerStatus.FINISHING)
    cancelling = State("Cancelling", SpectrometerStatus.CANCELLING)
    # The manual also describes an "Undefined" state, which we aren't using

    _start_connecting = idle.to(connecting)
    _finish_connecting = connecting.to(connected)

    start = connected.to(measuring)
    _start_finishing_measuring = measuring.to(finishing)
    _finish_measuring = finishing.to(connected)
    _cancel_measuring = measuring.to(cancelling)
    _reset_after_cancelling = cancelling.to(connected)

    def __init__(self, measure_duration: float) -> None:
        """Create a new OPUSStateMachine.

        The state diagram looks like this:

        ![](../../../../../OPUSStateMachine.png)

        Args:
            measure_duration: How long a single measurement takes (seconds)
        """
        self.measure_timer = QTimer()
        """Timer signalling the end of a measurement."""
        self.measure_timer.setInterval(round(measure_duration * 1000))
        self.measure_timer.setSingleShot(True)
        self.measure_timer.timeout.connect(self._on_measure_finished)

        super().__init__()

    def connect(self) -> None:
        """Connect to the device."""
        self._start_connecting()
        self._finish_connecting()

    def stop(self) -> None:
        """Stop the current measurement."""
        self._cancel_measuring()
        self._reset_after_cancelling()
        logging.info("Cancelling current measurement")

    def _on_measure_finished(self) -> None:
        """Finish measurement successfully."""
        self._start_finishing_measuring()
        self._finish_measuring()

    def on_enter_measuring(self) -> None:
        """Start the measurement timer."""
        self.measure_timer.start()

    def on_exit_measuring(self) -> None:
        """Stop the measurement timer."""
        self.measure_timer.stop()


class DummyOPUSInterface(
    OPUSInterfaceBase,
    description="Dummy OPUS device",
    parameters={"measure_duration": "Measurement duration in seconds"},
):
    """A mock version of the OPUS API for testing purposes."""

    _COMMAND_ERRORS: ClassVar = {
        "cancel": OPUSErrorInfo.NOT_RUNNING,
        "stop": OPUSErrorInfo.NOT_RUNNING_OR_FINISHING,
        "start": OPUSErrorInfo.NOT_CONNECTED,
        "connect": OPUSErrorInfo.NOT_IDLE,
    }
    """The error thrown by each command when in an invalid state."""

    def __init__(self, measure_duration: float = 1.0) -> None:
        """Create a new DummyOPUSInterface.

        Args:
            measure_duration: How long a single measurement takes (seconds)
        """
        super().__init__()

        self.state_machine = OPUSStateMachine(measure_duration)
        """An object representing the internal state of the device."""

        # Monitor state changes
        self.state_machine.add_observer(self)

        # Broadcast initial status
        self.on_enter_state(self.state_machine.current_state)

    def close(self) -> None:
        """Close the device.

        If a measurement is running, cancel it.
        """
        self.state_machine.measure_timer.stop()
        super().close()

    def _run_command(self, command: str) -> None:
        """Try to run the specified command.

        If the device is not in the correct state, self.last_error will be changed.

        Args:
            command: The command to run
        """
        fun = getattr(self.state_machine, command)

        try:
            fun()
        except TransitionNotAllowed:
            self._COMMAND_ERRORS[command].raise_exception()

    def request_command(self, command: str) -> None:
        """Execute the specified command on the device.

        Args:
            command: The command to run
        Raises:
            OPUSError: If the device is in the wrong state for this command
        """
        if command not in self._COMMAND_ERRORS:
            OPUSErrorInfo.UNKNOWN_COMMAND.raise_exception()

        self._run_command(command)

    def on_enter_state(self, target: State) -> None:
        """Broadcast state changes via pubsub."""
        self.send_status_message(target.value)
