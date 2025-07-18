"""This module provides an interface to TC4820 temperature controllers.

Decimal numbers are used for values sent to and read from the device as the values are
base-10 and using floats could cause rounding errors.

There are broadly two serial-related exceptions that are raised by this module.
MalformedMessageErrors are raised when a message is corrupted and are recoverable (i.e.
you can try submitting the request again). serial.SerialExceptions indicate that an
IO error occurred while communicating with the device (e.g. because a USB cable has
become disconnected) and are unlikely to be recoverable. A SerialException is also
raised if multiple attempts at a request have failed.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from serial import SerialException

from frog.hardware.plugins.temperature.temperature_controller_base import (
    TemperatureControllerBase,
)
from frog.hardware.serial_device import SerialDevice

MAX_POWER = 511


class MalformedMessageError(Exception):
    """Raised when a message sent or received was malformed."""


class TC4820(SerialDevice, TemperatureControllerBase, description="TC4820"):
    """An interface for TC4820 temperature controllers."""

    def __init__(
        self, name: str, port: str, baudrate: int = 115200, max_attempts: int = 3
    ) -> None:
        """Create a new TC4820 from an existing serial device.

        Args:
            name: The name of the device, to distinguish it from others
            port: Description of USB port (vendor ID + product ID)
            baudrate: Baud rate of port
            max_attempts: Maximum number of attempts for requests
        """
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        self.max_attempts = max_attempts

        SerialDevice.__init__(self, port, baudrate)
        TemperatureControllerBase.__init__(self, name)

    def close(self) -> None:
        """Close the device."""
        TemperatureControllerBase.close(self)
        SerialDevice.close(self)

    def read_int(self) -> int:
        """Read a message from the TC4820 and decode the number as a signed integer.

        Valid messages have the form "*{number}{checksum}^", where {number} is a signed
        integer represented as a zero-padded four-char hexadecimal number and {checksum}
        is the checksum for this message, represented as a zero-padded two-char
        hexadecimal number (see checksum() function for details). Negative numbers are
        represented as if they had been cast to an unsigned integer before being encoded
        as hex (i.e. -1 is represented as "ffff").

        There is one special message "*XXXX60^", which is what the device sends when the
        checksum for the last message we sent didn't match.

        If we receive a malformed message or "*XXXX60^", a MalformedMessageError is
        raised. A SerialException can also be raised by the underlying PySerial library,
        which indicates that a lower-level IO error has occurred (e.g. because the USB
        cable has become disconnected).

        Raises:
            MalformedMessageError: The read message was malformed or the device is
                                   complaining that our message was malformed
            SerialException: An error occurred while reading the device
        """
        message_bytes = self.serial.read_until(b"^", size=8)

        # Don't handle decoding errors, because these will be caught by bytes.fromhex()
        # below
        message = message_bytes.decode("ascii", errors="replace")

        if len(message) != 8 or message[0] != "*" or message[-1] != "^":
            raise MalformedMessageError(f"Malformed message received: {message}")

        if message == "*XXXX60^":
            raise MalformedMessageError("Bad checksum sent")

        if message[5:7] != self.checksum(message[1:5]):
            raise MalformedMessageError("Bad checksum received")

        try:
            # Turn the hex string into raw bytes...
            int_bytes = bytes.fromhex(message[1:5])
        except ValueError as e:
            raise MalformedMessageError("Number was not provided as hex") from e

        # ...then convert the raw bytes to a signed int
        return int.from_bytes(int_bytes, byteorder="big", signed=True)

    def send_command(self, command: str) -> None:
        r"""Write a message to the TC4820.

        The command is usually an integer represented as a zero-padded six-char
        hexadecimal string.

        Sent messages are encoded similarly (but not identically) to those received and
        look like "*{command}{checksum}\r", where the checksum is calculated as it is
        for received messages.

        Args:
            command: The string command to send
        Raises:
            SerialException: An error occurred while writing to the device
        """
        checksum = self.checksum(command)
        message = f"*{command}{checksum}\r"
        self.serial.write(message.encode("ascii"))

    def request_int(self, command: str) -> int:
        """Write the specified command then read an int from the device.

        If the request fails because a malformed message was received or the device
        indicates that our message was corrupted, then retransmission will be attempted
        a maximum of self.max_attempts times.

        Raises:
            SerialException: An error occurred while communicating with the device or
                             max attempts was exceeded
        """
        for _ in range(self.max_attempts):
            self.send_command(command)

            try:
                return self.read_int()
            except MalformedMessageError as e:
                logging.warn(f"Malformed message: {e!s}; retrying")

        raise SerialException(
            f"Maximum number of attempts (={self.max_attempts}) exceeded"
        )

    def request_decimal(self, command: str) -> Decimal:
        """Write the specified command then read a Decimal from the device.

        If the request fails because of a checksum failure, then retransmission will be
        attempted a maximum of self.max_attempts times.

        Raises:
            SerialException: An error occurred while communicating with the device or
                             max attempts was exceeded
        """
        return self.to_decimal(self.request_int(command))

    @property
    def temperature(self) -> Decimal:
        """The current temperature reported by the device."""
        return self.request_decimal("010000")

    @property
    def power(self) -> float:
        """The current power output of the device, as a percentage of maximum."""
        return self.request_int("020000") * 100.0 / MAX_POWER

    @property
    def alarm_status(self) -> int:
        """The current error status of the system.

        A value of zero indicates that no error has occurred.

        TODO: Figure out what the error codes mean
        """
        return self.request_int("030000")

    @property
    def set_point(self) -> Decimal:
        """The set point temperature (in degrees).

        In other words, this indicates the temperature the device is aiming towards.
        """
        return self.request_decimal("500000")

    @set_point.setter
    def set_point(self, temperature: Decimal) -> None:
        # Convert to an int for transmission
        val = round(temperature * Decimal(10))

        # Values outside this range can't be properly encoded
        if val < 0 or val > 0xFFFF:
            raise ValueError("Temperature provided is out of range")

        # Request that the device changes the set point and confirm that the returned
        # value is what we asked for
        if self.request_int(f"1c{val:0{4}x}") != val:
            logging.warn(
                "The set point returned by the device differs from the one requested"
            )

    @staticmethod
    def checksum(message: str) -> str:
        """Calculate a checksum for a message sent or received."""
        csum = sum(message.encode("ascii")) & 0xFF
        return f"{csum:0{2}x}"

    @staticmethod
    def to_decimal(value: int) -> Decimal:
        """Convert an int from the TC4820 to a Decimal."""
        # Decimal values are encoded as 10x their value then converted to an int.
        return Decimal(value) / Decimal(10)
