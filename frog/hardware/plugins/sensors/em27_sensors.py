"""This module provides an interface to the EM27 monitor.

This is used to scrape the PSF27Sensor data table off the server.
"""

from decimal import Decimal

from frog.config import (
    DEFAULT_HTTP_TIMEOUT,
    EM27_HOST,
    EM27_SENSORS_POLL_INTERVAL,
    EM27_SENSORS_URL,
)
from frog.hardware.device import DeviceClassType
from frog.hardware.http_device import HTTPDevice
from frog.hardware.plugins.sensors.sensors_base import SensorsBase
from frog.sensor_reading import SensorReading


def get_em27_sensor_data(content: str) -> list[SensorReading]:
    """Search for the PSF27Sensor table and store the data.

    Args:
        content: HTML content in which to search for PSF27Sensor table

    Returns:
        data_table: a list of sensor properties and their values
    """
    table_header = (
        "<TR><TH>No</TH><TH>Name</TH><TH>Description</TH>"
        + "<TH>Status</TH><TH>Value</TH><TH>Meas. Unit</TH></TR>"
    )
    table_start = content.find(table_header)
    if table_start == -1:
        raise EM27Error("PSF27Sensor table not found")

    table_end = table_start + content[table_start:].find("</TABLE>")
    table = content[table_start:table_end].splitlines()
    data_table = []
    for row in range(1, len(table)):
        data_table.append(
            SensorReading(
                table[row].split("<TD>")[2].rstrip("</TD>"),
                Decimal(table[row].split("<TD>")[5].strip("</TD>")),
                table[row].split("<TD>")[6].rstrip("</TD></TR"),
            )
        )

    return data_table


class EM27Error(Exception):
    """Indicates than an error occurred while parsing the webpage."""


class EM27SensorsBase(
    HTTPDevice,
    SensorsBase,
    class_type=DeviceClassType.IGNORE,
    async_open=True,
):
    """An interface for monitoring EM27 properties."""

    def __init__(
        self,
        url: str,
        poll_interval: float = float("nan"),
        timeout: float = DEFAULT_HTTP_TIMEOUT,
    ) -> None:
        """Create a new EM27 property monitor.

        Args:
            url: Web address of the automation units diagnostics page.
            poll_interval: How often to poll the device (seconds)
            timeout: The maximum time in seconds to wait for a response from the server
        """
        self._url: str = url
        self._connected = False

        HTTPDevice.__init__(self, timeout)
        SensorsBase.__init__(self, poll_interval)

        self.request_readings()

    def request_readings(self) -> None:
        """Request the EM27 property data from the web server.

        The HTTP request is made on a background thread.
        """
        self.make_request(self._url)

    def handle_response(self, response: str):
        """Process received sensor data."""
        readings = get_em27_sensor_data(response)

        if not self._connected:
            self._connected = True
            self.signal_is_opened()
            self.start_polling()

        self.send_readings_message(readings)


class EM27Sensors(
    EM27SensorsBase,
    description="EM27 sensors",
    parameters={"host": "The IP address or hostname of the EM27 device"},
):
    """An interface for EM27 sensors on the real device."""

    def __init__(
        self,
        host: str = EM27_HOST,
        poll_interval: float = EM27_SENSORS_POLL_INTERVAL,
        timeout: float = DEFAULT_HTTP_TIMEOUT,
    ) -> None:
        """Create a new EM27Sensors.

        Args:
            host: The IP address or hostname of the EM27 device
            poll_interval: How often to poll the sensors (seconds)
            timeout: The maximum time in seconds to wait for a response from the server
        """
        super().__init__(EM27_SENSORS_URL.format(host=host), poll_interval, timeout)
