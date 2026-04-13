"""This module provides an interface to Seneca temperature readers."""

import logging
from collections.abc import Sequence

import numpy
from crc import Calculator, Crc16

from frog.config import (
    Z8AI_MAX_MILLIVOLT,
    Z8AI_MAX_TEMP,
    Z8AI_MIN_MILLIVOLT,
    Z8AI_MIN_TEMP,
)
from frog.hardware.device import DeviceError, retry_request
from frog.hardware.plugins.temperature.temperature_monitor_base import (
    TemperatureMonitorBase,
)
from frog.hardware.serial_device import SerialDevice


def calculate_crc(data: bytes) -> int:
    """Perform cyclic redundancy check (crc).

    Args:
        data: The message to check

    Returns:
        crc: The calculated checksum
    """
    calculator = Calculator(Crc16.MODBUS)  # type: ignore
    checksum = calculator.checksum(data[:-2])
    return checksum


class Z8AIError(DeviceError):
    """Indicates that an error occurred while communicating with the device."""


class Z8AI(
    SerialDevice,
    TemperatureMonitorBase,
    description="Seneca Z-8AI",
    parameters={
        "min_temp": "The minimum temperature limit of the device",
        "max_temp": "The maximum temperature limit of the device",
        "min_millivolt": "The minimum voltage output (millivolts) of the device",
        "max_millivolt": "The maximum voltage output (millivolts) of the device",
        "max_attempts": "Maximum number of attempts for requests",
    },
):
    """An interface for the Seneca Z-8AI analogue input module.

    This device communicates through the MODBUS-RTU protocol and outputs data from
    temperature monitor devices. The current connected temperature monitor device is
    the Seneca T121.

    The manual for this device is available at:
    https://www.seneca.it/en/linee-di-prodotto/acquisizione-dati-e-automazione/sistemi-io-modbus-rtu/moduli-io-analogici/z-8ai
    """

    def __init__(
        self,
        hot_bb_channel: str,
        cold_bb_channel: str,
        port: str,
        baudrate: int = 57600,
        min_temp: int = Z8AI_MIN_TEMP,
        max_temp: int = Z8AI_MAX_TEMP,
        min_millivolt: int = Z8AI_MIN_MILLIVOLT,
        max_millivolt: int = Z8AI_MAX_MILLIVOLT,
        max_attempts: int = 3,
    ) -> None:
        """Create a new Z8AI.

        Args:
            hot_bb_channel: Channel name for hot black body
            cold_bb_channel: Channel name for cold black body
            port: Description of USB port (vendor ID + product ID)
            baudrate: Baud rate of port
            min_temp: The minimum temperature limit of the device.
            max_temp: The maximum temperature limit of the device.
            min_millivolt: The minimum voltage output (millivolts) of the device.
            max_millivolt: The maximum voltage output (millivolts) of the device.
            max_attempts: Maximum number of attempts for requests.
        """
        SerialDevice.__init__(self, port, baudrate)
        TemperatureMonitorBase.__init__(
            self, hot_bb_channel=hot_bb_channel, cold_bb_channel=cold_bb_channel
        )

        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        self.max_attempts = max_attempts
        self.MIN_TEMP = min_temp
        self.MAX_TEMP = max_temp
        self.MIN_MILLIVOLT = min_millivolt
        self.MAX_MILLIVOLT = max_millivolt

        # The temperature range divided by the voltage range.
        # This figure is used when converting the raw data to temperatures.
        temp_range = self.MAX_TEMP - self.MIN_TEMP
        millivolt_range = self.MAX_MILLIVOLT - self.MIN_MILLIVOLT
        self.SCALING_FACTOR = temp_range / millivolt_range

    def read(self) -> bytes:
        """Read temperature data from the Z-8AI.

        Returns:
            data: The sequence of bytes read from the device

        Raises:
            SerialException: Error reading from the device
            Z8AIError: Malformed message received from device
        """
        # require 21 bytes else checks will fail
        min_length = 21
        data = self.serial.read(size=min_length)

        if len(data) != min_length:
            raise Z8AIError("Insufficient data read from device")

        return data

    def request_read(self) -> None:
        """Write a message to the Z-8AI to prepare for a read operation.

        A byte array of [1, 3, 0, 2, 0, 8, 229, 204] is written to the device as a
        request to read the data. This byte array was taken from the original C# code.

        Raises:
            SerialException: Error writing to the device
        """
        self.serial.write(bytearray([1, 3, 0, 2, 0, 8, 229, 204]))

    def parse_data(self, data: bytes) -> numpy.ndarray:
        """Parse temperature data read from the Z-8AI.

        The sequence of bytes is put through the conversion function and translated into
        floats.

        Args:
            data: The bytes read from the device.

        Returns:
            An array containing the temperature values recorded by the Z-8AI device.

        Raises:
            Z8AIError: CRC validation failed
        """
        crc = calculate_crc(data)
        check = numpy.frombuffer(data[19:], numpy.dtype(numpy.uint16))

        if crc != check:
            raise Z8AIError("CRC check failed")

        # Changes byte order as data read from device is in big-endian format
        dt = numpy.dtype(numpy.uint16).newbyteorder(">")

        # Converts incoming bytes into 16-bit ints
        ints = numpy.frombuffer(data, dt, 8, 3)

        return self.calc_temp(ints)

    def calc_temp(self, vals: numpy.ndarray) -> numpy.ndarray:
        """Convert data read from the Z-8AI device into temperatures.

        Any readings outside the minimum and maximum temperature values will be changed
        to NaNs and a warning will be raised in the logs.

        Args:
            vals: The numpy array described by the data received from the device.

        Returns:
            The converted values.
        """
        # Convert from microvolts to millivolts
        calc = vals / 1000
        # Adjusts for minimum voltage limit
        calc -= self.MIN_MILLIVOLT
        # Scales for the device's dynamic range
        calc *= self.SCALING_FACTOR
        # Adjusts for minimum temperature limit
        calc += self.MIN_TEMP

        calc[calc > self.MAX_TEMP] = numpy.nan
        calc[calc < self.MIN_TEMP] = numpy.nan

        if numpy.isnan(calc).any():
            logging.warning(f"Out-of-range temperature(s) detected: {calc}")

        return calc

    def get_temperatures(self) -> Sequence:
        """Get the current temperatures."""

        def attempt() -> Sequence:
            self.request_read()
            data = self.read()
            return self.parse_data(data).tolist()

        return retry_request(attempt, self.max_attempts, Z8AIError)
