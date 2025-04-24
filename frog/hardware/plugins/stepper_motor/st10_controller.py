"""Code for interfacing with the ST10-Q-NN stepper motor controller.

Applied Motions have their own bespoke programming language ("Q") for interfacing with
their devices, of which we're only using a small portion here.

The specification is available online:
    https://appliedmotion.s3.amazonaws.com/Host-Command-Reference_920-0002W_0.pdf
"""

import logging
from enum import IntFlag
from queue import Queue

from PySide6.QtCore import QThread, QTimer, Signal
from serial import Serial, SerialException, SerialTimeoutException

from frog.config import STEPPER_MOTOR_HOMING_TIMEOUT
from frog.hardware.plugins.stepper_motor.stepper_motor_base import StepperMotorBase
from frog.hardware.serial_device import SerialDevice


class ST10ControllerError(SerialException):
    """Indicates that an error has occurred with the ST10 controller."""


class ST10AlarmCode(IntFlag):
    """The set of possible alarm codes for the ST10 motor controller.

    These values are taken from the manual. Note that the alarm code is a bit mask, so
    several of these may be set at once (if you're especially unlucky!).
    """

    POSITION_LIMIT = 0x0001
    CCW_LIMIT = 0x0002
    CW_LIMIT = 0x0004
    OVER_TEMP = 0x0008
    INTERNAL_VOLTAGE = 0x0010
    OVER_VOLTAGE = 0x0020
    UNDER_VOLTAGE = 0x0040
    OVER_CURRENT = 0x0080
    OPEN_MOTOR_WINDING = 0x0100
    BAD_ENCODER = 0x0200
    COMM_ERROR = 0x0400
    BAD_FLASH = 0x0800
    NO_MOVE = 0x1000
    BLANK_Q_SEGMENT = 0x4000

    def __str__(self) -> str:
        """Convert the set alarm code bits to a string."""
        error_str = ", ".join(code.name for code in self)  # type: ignore[misc]
        return f"Alarm code 0x{self:04X}: {error_str}"


_SEND_STRING_MAGIC = "Z"
"""The arbitrary magic string we are using for the send string command.

See ST10Controller._send_string() for details of this command.
"""


class _SerialReader(QThread):
    """For background reading from the serial device.

    There are two types of messages that we receive from the device. The first are
    immediately sent in response to a command sent to the controller, e.g. an ack
    message ("%"). This is what happens with all but one of the commands we are using.
    The one exception is the send string command ("SS"), which, in addition to eliciting
    an immediate ack (or nack) response, also leads to another response being sent when
    the motor has finished moving. Note that while the motor is moving, other commands
    can be sent and even processed, e.g. you can request that another move happens after
    the first is complete.

    All of the reading we do from the device goes via this class, as conceivably the
    magic send string response could be sent at any point after the send string command
    is sent, so reading should be continuous.

    When the magic send string response is received, the async_read_completed signal is
    emitted. Synchronous reads are handled by putting received messages into a Queue.
    """

    async_read_completed = Signal()
    """Indicates that an asynchronous read has finished."""

    read_error = Signal(BaseException)
    """Sent when an error occurs during reading."""

    def __init__(self, serial: Serial, sync_timeout: float) -> None:
        """Create a new _SerialReader.

        Args:
            serial: Serial device
            sync_timeout: Read timeout for synchronous requests
        """
        super().__init__()

        self.serial = serial
        self.sync_timeout = sync_timeout
        self.out_queue: Queue[str | BaseException] = Queue()
        self.stopping = False

    def quit(self) -> None:
        """Flag that the thread is stopping so we can ignore exceptions."""
        self.stopping = True
        super().quit()

    def _read(self) -> str:
        """Read the next message from the device.

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Malformed message received from device
        """
        raw = self.serial.read_until(b"\r")

        logging.debug(f"(ST10) <<< {raw!r}")

        try:
            return raw[:-1].decode("ascii")
        except UnicodeDecodeError:
            raise ST10ControllerError(f"Invalid message received: {raw!r}")

    def _read_error(self, error: BaseException) -> None:
        if self.stopping:
            return

        # Return the error synchronously to the first waiter
        self.out_queue.put(error)

        # Also send error as a signal as there is not necessarily a synchronous waiter
        self.read_error.emit(error)

    def _read_success(self, message: str) -> None:
        # The motor is signalling that it has finished moving
        if message == _SEND_STRING_MAGIC:
            self.async_read_completed.emit()
            return

        # Put message into queue to be retrieved by read_sync()
        self.out_queue.put(message)

    def _process_read(self) -> bool:
        """Process a single read, either synchronous or asynchronous."""
        try:
            message = self._read()
        except Exception as error:
            self._read_error(error)

            # TODO: Currently we abort if an I/O error occurs, though it may be possible
            # to recover in some situations
            return False

        self._read_success(message)
        return True

    def run(self) -> None:
        """Process reads in the background."""
        while self._process_read():
            pass

    def read_sync(self) -> str:
        """Read synchronously from the serial device."""
        try:
            response = self.out_queue.get(timeout=self.sync_timeout)
        except Exception:
            raise SerialTimeoutException()

        if isinstance(response, BaseException):
            raise response

        return response


class ST10Controller(
    SerialDevice, StepperMotorBase, description="ST10 controller", async_open=True
):
    """An interface for the ST10-Q-NN stepper motor controller.

    This class allows for moving the mirror to arbitrary positions and retrieving its
    current position.
    """

    STEPS_PER_ROTATION = 50800
    """The total number of steps in one full rotation of the mirror."""

    ST10_MODEL_ID = "107F024"
    """The model and revision number for the ST10 controller we are using."""

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 5.0) -> None:
        """Create a new ST10Controller.

        Args:
            port: Description of USB port (vendor ID + product ID)
            baudrate: Baud rate of port
            timeout: Connection timeout

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Malformed message received from device
        """
        SerialDevice.__init__(self, port, baudrate)

        self._reader = _SerialReader(self.serial, timeout)
        self._reader.async_read_completed.connect(self._on_initial_move_end)
        self._reader.read_error.connect(self.send_error_message)
        self._reader.start()

        self._init_error_timer = QTimer()
        """A timer to raise an error if the motor takes too long to move."""
        self._init_error_timer.setInterval(round(STEPPER_MOTOR_HOMING_TIMEOUT * 1000))
        self._init_error_timer.setSingleShot(True)
        self._init_error_timer.timeout.connect(
            lambda: self.send_error_message(
                RuntimeError("Timed out waiting for motor to move")
            )
        )

        # Check that we are connecting to an ST10
        self._check_device_id()

        self._disable_limit_switches()

        # Move mirror to home position
        self._home_and_reset()

        StepperMotorBase.__init__(self)

    def close(self) -> None:
        """Close device and leave mirror facing downwards.

        This prevents dust accumulating.
        """
        StepperMotorBase.close(self)

        if not self.serial.is_open:
            return

        # Don't handle move end events because they will likely happen after the device
        # is disconnected
        self._reader.async_read_completed.disconnect()

        try:
            self.stop_moving()
            self.move_to("nadir")
        except Exception as e:
            logging.error(f"Failed to reset mirror to downward position: {e}")

        # Set flag that indicates the thread should quit
        self._reader.quit()

        # If _reader is blocking on a read (which is likely), we could end up waiting
        # forever, so close the socket so that the read operation will terminate
        SerialDevice.close(self)

    def _on_initial_move_end(self) -> None:
        """Perform setup after motor's initial move has completed successfully."""
        # Move completed within time allotted
        self._init_error_timer.stop()

        # For future move end messages, use a different handler
        self._reader.async_read_completed.disconnect(self._on_initial_move_end)
        self._reader.async_read_completed.connect(self._on_move_end)

        # Signal that this device is ready to be used
        self.signal_is_opened()

    def _on_move_end(self) -> None:
        """Signal whether move was successful or an error occurred."""
        if alarm_code := self.alarm_code:
            # A controller error occurred
            self.send_error_message(ST10ControllerError(str(alarm_code)))
        else:
            # Move was successful
            self.send_move_end_message()

    def _check_device_id(self) -> None:
        """Check that the ID is the correct one for an ST10.

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: The device ID is not for an ST10
        """
        # Request model and revision
        self._write("MV")
        if self._read_sync() != self.ST10_MODEL_ID:
            raise ST10ControllerError("Device ID indicates this is not an ST10")

    def _disable_limit_switches(self) -> None:
        """Disable the limit switches on the controller.

        Without this, we get an error if the motor hits a limit switch. The limit
        switches aren't actually needed to protect anything in either the FINESSE or
        UNIRAS rigs (the worst that will happen is the motor will just spin around), so
        we don't need them.
        """
        # "Define limit". This command allows for setting the behaviour of the limit
        # switches. The "3" option means that they are treated as normal inputs.
        self._write_check("DL3")

    def _get_input_status(self, input: int) -> bool:
        """Read the status of the device's inputs.

        The inputs to the controller are boolean values, which include digital inputs,
        as well as other properties like alarm status. For a list of input values, see
        the manual.

        Args:
            input: Which input to retrieve value for
        """
        if input <= 0:
            raise ValueError("index must be greater than 0")

        input_status = self._request_value("IS")

        # The inputs are represented as ASCII zeroes and ones. The lowest input's value
        # is on the right.
        try:
            return input_status[-input] == "1"
        except IndexError:
            raise ValueError(f"index exceeded number of inputs ({len(input_status)})")

    @property
    def steps_per_rotation(self) -> int:
        """Get the number of steps that correspond to a full rotation."""
        return self.STEPS_PER_ROTATION

    def _home_and_reset(self) -> None:
        """Return the stepper motor to its home position and reset the counter.

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Malformed message received from device
        """
        # In case the motor is still moving, stop it now
        self.stop_moving()

        # If the homing switch is already active, move the motor a bit
        if self._get_input_status(6):
            self._relative_move(-5000)

        # Home the motor, leaving mirror facing upwards. The command means "seek home
        # until input 6 is high" (the input is an optoswitch).
        self._write_check("SH6H")

        # Turn mirror so it's facing down
        self._relative_move(-30130)

        # Tell the controller that this is step 0 ("set variable SP to 0")
        self._write_check("SP0")

        # Use a timer to show an error if the motor doesn't finish moving within the
        # given timeframe. (Note that the move commands are not run synchronously, so
        # this time is the time taken for all of these commands to finish.)
        self._init_error_timer.start()

        # Receive a notification when motor has finished moving
        self._notify_on_stopped()

    def _relative_move(self, steps: int) -> None:
        """Move the stepper motor to the specified relative position.

        Args:
            steps: Number of steps to move by

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Malformed message received from device
        """
        # "Feed to length"
        self._write_check(f"FL{steps}")

    @property
    def status_code(self) -> int:
        """The status code of the device.

        For a complete list of status codes and their meanings, consult the manual.
        """
        return self._request_int("SC", 16)

    @property
    def is_moving(self) -> bool:
        """Whether the motor is moving.

        This is done by checking whether the status code has the moving bit set.
        """
        return self.status_code & 0x0010 == 0x0010

    @property
    def alarm_code(self) -> ST10AlarmCode | None:
        """Get the current alarm code for the controller, if any."""
        code = self._request_int("AL", 16)
        return ST10AlarmCode(code) if code else None

    @property
    def step(self) -> int:
        """The current state of the device's step counter.

        This makes use of the "IP" command, which estimates the immediate position of
        the motor. If the motor is moving, this is an estimated (calculated trajectory)
        position. If the motor is stationary, this is the actual position.

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Malformed message received from device
        """
        return self._request_int("IP")

    @step.setter
    def step(self, step: int) -> None:
        """Move the stepper motor to the specified absolute position.

        Args:
            step: Which step position to move to

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Malformed message received from device
        """
        # "Feed to position"
        self._write_check(f"FP{step}")
        self._notify_on_stopped()

    def _send_string(self, string: str) -> None:
        """Request that the device sends string when operations have completed.

        The string is sent when the queue of move commands is empty and the motor has
        stopped moving.

        Args:
            string: String to be returned by the device
        """
        # "Send string"
        self._write_check(f"SS{string}")

    def _read_sync(self) -> str:
        """Read the next message from the device synchronously.

        Raises:
            SerialException: Error communicating with device
            ST10ControllerError: Malformed message received from device
        """
        return self._reader.read_sync()

    def _write(self, message: str) -> None:
        """Send the specified message to the device.

        Raises:
            SerialException: Error communicating with device
            UnicodeEncodeError: Malformed message
        """
        data = f"{message}\r".encode("ascii")
        logging.debug(f"(ST10) >>> {data!r}")
        self.serial.write(data)

    def _write_check(self, message: str) -> None:
        """Send the specified message and check whether the device returns an error.

        See _check_response().

        Args:
            message: ASCII-formatted message

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Malformed message received from device
            UnicodeEncodeError: Message to be sent is malformed
        """
        self._write(message)
        self._check_response()

    def _check_response(self) -> None:
        """Check whether the device has returned an error.

        There are two types of "success" response (ACK):
            - Normal acknowledge ("%"), indicating that the command was received and
              successfully executed
            - Exception acknowledge ("*"), indicating that the command was received and
              added to the execution buffer, i.e. it will be executed after other
              commands. (Why the manual uses the term "exception", who knows, but it
              also indicates success!)

        If an error occurs, the device returns a negative acknowledge (NACK) response,
        which is a "?", followed by an error code, e.g. "?4". The meanings of the error
        codes are listed in the manual linked in the module description.

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Error or malformed message
        """
        response = self._read_sync()

        # Either type of ACK response is acceptable
        if response in ("%", "*"):
            return

        # An error occurred (NACK)
        if response[0] == "?":
            raise ST10ControllerError(
                f"Device returned an error (code: {response[1:]})"
            )

        raise ST10ControllerError(f"Unexpected response from device: {response}")

    def _request_value(self, name: str) -> str:
        """Request a named value from the device.

        You can request the values of various variables, which all seem to have
        two-letter names.

        Args:
            name: Variable name

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Malformed message received from device
            UnicodeEncodeError: Message to be sent is malformed
        """
        self._write(name)
        response = self._read_sync()
        if not response.startswith(f"{name}="):
            raise ST10ControllerError(f"Unexpected response when querying value {name}")

        return response[len(name) + 1 :]

    def _request_int(self, name: str, base: int = 10) -> int:
        """Request a named value from the device and interpret the result as an int.

        Args:
            name: Variable name
            base: Base of integer (e.g. 16 for hexadecimal)

        Raises:
            SerialException: Error communicating with device
            SerialTimeoutException: Timed out waiting for response from device
            ST10ControllerError: Malformed message received from device
            UnicodeEncodeError: Message to be sent is malformed

        Returns:
            int: The integer corresponding to the named value
        """
        resp = self._request_value(name)
        try:
            return int(resp, base)
        except ValueError:
            raise ST10ControllerError(f"Non-integer response received ({resp})")

    def stop_moving(self) -> None:
        """Immediately stop moving the motor."""
        self._write_check("ST")

    def _notify_on_stopped(self) -> None:
        """Wait until the motor has stopped moving and send a message when done."""
        self._send_string(_SEND_STRING_MAGIC)
