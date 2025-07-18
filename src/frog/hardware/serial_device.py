"""Provides a base class for USB serial devices."""

from __future__ import annotations

import logging
import re

from serial import Serial, SerialException
from serial.tools.list_ports import comports

from frog.config import BAUDRATES
from frog.hardware.device import AbstractDevice

_serial_ports: dict[str, str] | None = None


def _port_info_to_str(vendor_id: int, product_id: int, count: int = 0) -> str:
    """Convert USB port information to a formatted string.

    Args:
        vendor_id: USB vendor ID
        product_id: USB product ID
        count: Extra field to distinguish devices
    """
    out = f"{vendor_id:04x}:{product_id:04x}"
    if count > 0:
        out += f" ({count + 1})"
    return out


def _get_port_parts(port: str) -> tuple[str, int]:
    """Split the port name into the string prefix and the number suffix.

    If there is no number at the end of the string, (port, -1) will be returned.
    """
    match = re.match("^([^0-9])*([0-9]*)$", port)

    # NB: This should never fail as the regex should encompass all strings
    assert match, "Invalid port name"

    num_str = match.group(2)
    num = int(num_str) if num_str else -1

    return match.group(1), num


def _get_usb_serial_ports(refresh: bool = False) -> dict[str, str]:
    """Get the ports for connected USB serial devices.

    The list of ports is only requested from the OS once and the result is cached,
    unless the refresh argument is set to true.

    Args:
        refresh: Refresh the list of serial ports even if they have already been
                 requested
    """
    global _serial_ports
    if _serial_ports is not None and not refresh:
        return _serial_ports

    # Keep track of ports with the same vendor and product ID and assign them an
    # additional number to distinguish them
    counter: dict[tuple[int, int], int] = {}
    _serial_ports = {}
    for port in sorted(comports(), key=lambda port: _get_port_parts(port.device)):
        # Vendor ID is a USB-specific field, so we can use this to check whether the
        # device is USB or not
        if port.vid is None:
            continue

        key = (port.vid, port.pid)
        if key not in counter:
            counter[key] = 0

        _serial_ports[_port_info_to_str(*key, counter[key])] = port.device
        counter[key] += 1

    if not _serial_ports:
        logging.warning("No USB serial devices found")
    else:
        port_strs = "".join(
            f"\n\t- {port}: {desc}" for desc, port in _serial_ports.items()
        )
        logging.info(f"Found the following USB serial devices:{port_strs}")

    # Sort by the string representation of the key
    _serial_ports = dict(sorted(_serial_ports.items(), key=lambda item: item[0]))

    return _serial_ports


def _create_serial(port: str, baudrate: int, refresh: bool) -> Serial:
    """Create a new serial device and connect to it.

    Args:
        port: Description of USB port (vendor ID + product ID)
        baudrate: Baud rate of port
        refresh: Whether to force-refresh the list of COM ports
    """
    devices = _get_usb_serial_ports(refresh)

    try:
        device = devices[port]
    except KeyError:
        raise SerialException(f'Device not present: "{port!s}"')
    else:
        return Serial(port=device, baudrate=baudrate)


class SerialDevice(
    AbstractDevice,
    parameters={
        "port": (
            "USB port (vendor and product ID)",
            tuple(_get_usb_serial_ports().keys()),
        ),
        "baudrate": ("Baud rate", BAUDRATES),
    },
):
    """A base class for USB serial devices.

    Note that it is not sufficient for a device type class to inherit from this class
    alone: it must also inherit from a device base class. When doing so, this class
    *must* be listed before any other parent classes, otherwise the ABC won't be able to
    find this class's implementation of close() and will complain about missing
    functions.
    """

    serial: Serial
    """Underlying serial device."""

    def __init__(self, port: str, baudrate: int) -> None:
        """Create a new serial device.

        Args:
            port: Description of USB port (vendor ID + product ID)
            baudrate: Baud rate of port
        """
        # If port is unknown, it may be because the user connected the device after the
        # list of serial ports was retrieved, so we refresh the list to check if it is
        # now available. Similarly, the COM port may have changed due to the user
        # disconnecting and reconnecting the device, in which case we also need to
        # refresh the list.
        try:
            self.serial = _create_serial(port, baudrate, refresh=False)
        except SerialException:
            self.serial = _create_serial(port, baudrate, refresh=True)

    def close(self) -> None:
        """Close the connection to the device."""
        self.serial.close()
