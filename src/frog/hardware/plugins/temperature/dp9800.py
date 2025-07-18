"""This module provides an interface to DP9800 temperature readers."""

from collections.abc import Sequence
from decimal import Decimal

from serial import SerialException

from frog.hardware.plugins.temperature.temperature_monitor_base import (
    TemperatureMonitorBase,
)
from frog.hardware.serial_device import SerialDevice


def check_data(data: bytes) -> None:
    """Perform message integrity checks.

    Check characters that we know should be constant. The message should
    start with STX, end with NUL and contain an ETX. The exact position
    of ETX is uncertain since it depends on the width of the BCC.

    Args:
        data: the message to check

    Raises:
        DP9800Error: Malformed message received from device
    """
    if data[0] != 2:  # STX
        raise DP9800Error("Start transmission character not detected")
    if data.find(3) == -1:  # ETX
        raise DP9800Error("End transmission character not detected")
    if data[-1] != 0:  # NUL
        raise DP9800Error("Null terminator not detected")


def calculate_bcc(data: bytes) -> int:
    """Calculate block check character.

    Args:
        data: the message to check

    Returns:
        bcc: block check character
    """
    bcc_chars = data[1:-2]
    bcc = 0
    for byte in bcc_chars:
        bcc ^= byte

    return bcc


def parse_data(data: bytes) -> tuple[list[Decimal], str]:
    """Parse temperature data read from the DP9800.

    The sequence of bytes is translated into a list of ASCII strings
    representing each of the temperatures, and finally into floats.

    Returns:
        vals: A list of Decimals containing the temperature values recorded
              by the DP9800 device.
        sysflag: string representation of the system flag bitmask
    """
    check_data(data)
    bcc = calculate_bcc(data)
    if bcc != data[-2]:
        raise DP9800Error("BCC check failed")

    try:
        data_ascii = data.decode("ascii")
    except UnicodeDecodeError as e:
        raise DP9800Error(e)

    vals_begin = 2  # Following STX T
    vals_end = 74  # Following STX T (%8.2f)*9, assuming 9 vals
    etx_index = data.find(b"\x03")

    vals = [Decimal(val) for val in data_ascii[vals_begin:vals_end].split()]

    sysflag = bin(int(data_ascii[vals_end:etx_index], 16))

    # Omit mysterious first temperature, and omit binary identifier characters
    return vals[1:], sysflag[2:]


class DP9800Error(Exception):
    """Indicates that an error occurred while communicating with the device."""


class DP9800(SerialDevice, TemperatureMonitorBase, description="DP9800"):
    """An interface for DP9800 temperature readers.

    The manual for this device is available at:
    https://assets.omega.com/manuals/M5210.pdf
    """

    def __init__(self, port: str, baudrate: int = 38400) -> None:
        """Create a new DP9800.

        Args:
            port: Description of USB port (vendor ID + product ID)
            baudrate: Baud rate of port
        """
        SerialDevice.__init__(self, port, baudrate)
        TemperatureMonitorBase.__init__(self)

    def get_device_settings(self, sysflag: str) -> dict[str, str]:
        """Provide the settings of the device as stored in the system flag.

        The system flag is stored as a bit mask with the format TxxLxSAF,
        where:
            F - bit 0: temperature unit: 0 = deg C, 1 = deg F
            A - bit 1: audible button:   0 = silence, 1 = audible
            S - bit 2: autoscan:         0 = no scan, 1 = autoscan active
            x - bit 3: must be 0
            L - bit 4: logging:          0 = no logging, 1 = logging active
            x - bit 5: must be 0
            x - bit 6: must be 0
            T - bit 7: instrument type:  0 = TC, 1 = PT

        Args:
            sysflag: string representation of the system flag bitmask

        Returns:
            dictionary containing the current device settings
        """
        return {
            "instrument_type": ["TC", "PT"][int(sysflag[0])],
            "logging_state": ["no logging", "logging active"][int(sysflag[3])],
            "scanning_state": ["no scan", "autoscan active"][int(sysflag[5])],
            "audible_state": ["silence", "audible"][int(sysflag[6])],
            "temperature_unit": ["deg C", "deg F"][int(sysflag[7])],
        }

    def read_temperature_data(self) -> bytes:
        """Read temperature data from the DP9800.

        The DP9800 returns a sequence of bytes containing the
        temperatures measured on each channel, in the format

          STX T t1 t2 t3 t4 t5 t6 t7 t8 t9 ff ETX BCC NUL

        where
            t1, t2, ..., t9: temperature values in the format %8.2f
            STX: Start of Text (ASCII 2)
            ETX: End of Text (ASCII 3)
            NUL: Null character (ASCII 0)
            BCC: Block Check Character
            ff: System flag in hexadecimal

        For error checking, the BCC is calculated by performing consecutive XOR
        operations on the message and compared with the BCC received.

        Note a slight peculiarity:
        The device actually returns 9 temperatures, while the documentation
        states that there should be 8. The device shows 8 values, corresponding
        to the values with indices 1 to 8. The first value (at index 0) is
        therefore ignored.

        Returns:
            data: the sequence of bytes read from the device

        Raises:
            DP9800Error: Malformed message received from device
        """
        try:
            data = self.serial.read_until(b"\x00")
        except SerialException as e:
            raise DP9800Error(e)

        # require at least 4 bytes else checks will fail
        min_length = 4
        if len(data) < min_length:
            raise DP9800Error("Insufficient data read from device")

        return data

    def request_read(self) -> None:
        """Write a message to the DP9800 to prepare for a read operation.

        Format:

          EOT T ENQ

        EOT: End of Transmission (ASCII 4)
        ENQ: Enquiry (ASCII 5)

        Raises:
            DP9800Error: Error writing to the device
        """
        try:
            self.serial.write(b"\x04T\x05")
        except Exception as e:
            raise DP9800Error(e)

    def get_temperatures(self) -> Sequence:
        """Get the current temperatures."""
        self.request_read()
        data = self.read_temperature_data()
        temperatures, _ = parse_data(data)
        return temperatures
