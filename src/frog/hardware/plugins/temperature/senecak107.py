"""This module provides an interface to Seneca temperature readers."""

import logging
from collections.abc import Sequence

import numpy
from crc import Calculator, Crc16
from serial import SerialException

from frog.config import (
    SENECA_MAX_MILLIVOLT,
    SENECA_MAX_TEMP,
    SENECA_MIN_MILLIVOLT,
    SENECA_MIN_TEMP,
)
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


class SenecaK107Error(Exception):
    """Indicates that an error occurred while communicating with the device."""


class SenecaK107(
    SerialDevice,
    TemperatureMonitorBase,
    description="Seneca K107",
    parameters={
        "min_temp": "The minimum temperature limit of the device",
        "max_temp": "The maximum temperature limit of the device",
        "min_millivolt": "The minimum voltage output (millivolts) of the device",
        "max_millivolt": "The maximum voltage output (millivolts) of the device",
    },
):
    """An interface for the Seneca K107USB serial converter.

    This device communicates through the MODBUS-RTU protocol and outputs data from
    temperature monitor devices. The current connected temperature monitor device is
    the Seneca T121.

    The manual for this device is available at:
    https://www.seneca.it/products/k107usb/doc/installation_manualEN
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 57600,
        min_temp: int = SENECA_MIN_TEMP,
        max_temp: int = SENECA_MAX_TEMP,
        min_millivolt: int = SENECA_MIN_MILLIVOLT,
        max_millivolt: int = SENECA_MAX_MILLIVOLT,
    ) -> None:
        """Create a new SenecaK107.

        Args:
            port: Description of USB port (vendor ID + product ID)
            baudrate: Baud rate of port
            min_temp: The minimum temperature limit of the device.
            max_temp: The maximum temperature limit of the device.
            min_millivolt: The minimum voltage output (millivolts) of the device.
            max_millivolt: The maximum voltage output (millivolts) of the device.
        """
        SerialDevice.__init__(self, port, baudrate)
        TemperatureMonitorBase.__init__(self)

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
        """Read temperature data from the SenecaK107.

        Returns:
            data: The sequence of bytes read from the device

        Raises:
            SenecaK107Error: Malformed message received from device
        """
        try:
            data = self.serial.read(size=21)
        except SerialException as e:
            raise SenecaK107Error(e)

        # require 21 bytes else checks will fail
        min_length = 21
        if len(data) != min_length:
            raise SenecaK107Error("Insufficient data read from device")

        return data

    def request_read(self) -> None:
        """Write a message to the SenecaK107 to prepare for a read operation.

        A byte array of [1, 3, 0, 2, 0, 8, 229, 204] is written to the device as a
        request to read the data. This byte array was taken from the original C# code.

        Raises:
            SenecaK107Error: Error writing to the device
        """
        try:
            self.serial.write(bytearray([1, 3, 0, 2, 0, 8, 229, 204]))
        except Exception as e:
            raise SenecaK107Error(e)

    def parse_data(self, data: bytes) -> numpy.ndarray:
        """Parse temperature data read from the SenecaK107.

        The sequence of bytes is put through the conversion function and translated
        into floats.

        Args:
            data: The bytes read from the device.

        Returns:
            An array containing the temperature values recorded
                by the SenecaK107 device.
        """
        crc = calculate_crc(data)
        check = numpy.frombuffer(data[19:], numpy.dtype(numpy.uint16))

        if crc != check:
            raise SenecaK107Error("CRC check failed")

        # Changes byte order as data read from device is in big-endian format
        dt = numpy.dtype(numpy.uint16).newbyteorder(">")

        # Converts incoming bytes into 16-bit ints
        ints = numpy.frombuffer(data, dt, 8, 3)

        return self.calc_temp(ints)

    def calc_temp(self, vals: numpy.ndarray) -> numpy.ndarray:
        """Convert data read from the SenecaK107 device into temperatures.

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
        self.request_read()
        data = self.read()
        return self.parse_data(data).tolist()
