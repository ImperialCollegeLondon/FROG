"""This module contains code for interfacing with different hardware devices."""
import sys

from pubsub import pub

if "--dummy-em27" in sys.argv:
    from .dummy_em27_scraper import DummyEM27Scraper as EM27Scraper
    from .opus.dummy import DummyOPUSInterface as OPUSInterface
else:
    from .em27_scraper import EM27Scraper  # type: ignore
    from .opus.em27 import OPUSInterface  # type: ignore

from finesse.device_type import DeviceType

from . import data_file_writer  # noqa: F401
from .plugins import load_device_types
from .plugins.stepper_motor import create_stepper_motor_serial_manager
from .plugins.temperature import (
    create_temperature_controller_serial_managers,
    create_temperature_monitor_serial_manager,
)

opus: OPUSInterface


def _broadcast_device_types() -> None:
    """Broadcast the available device types via pubsub."""
    # Use a dict keyed by the base type containing info about each device type
    device_types: dict[str, list[DeviceType]] = {}
    for names, types in load_device_types().values():
        key = types[0]._device_base_description
        dtypes = [
            DeviceType(t._device_description, t._device_parameters) for t in types
        ]

        if not names:
            device_types[key] = dtypes
        else:
            # If there can be multiple uses of a given device (e.g. temperature
            # controllers for hot and cold black bodies), give the device types
            # different names.
            #
            # TODO: Use human-readable names for this rather than topic names
            for name in names:
                device_types[f"{key} ({name})"] = dtypes

    pub.sendMessage("serial.list", device_types=device_types)


def _init_hardware():
    global opus

    opus = OPUSInterface()
    _broadcast_device_types()


def _stop_hardware():
    global opus
    del opus


pub.subscribe(_init_hardware, "window.opened")
pub.subscribe(_stop_hardware, "window.closed")

scraper = EM27Scraper()
create_stepper_motor_serial_manager()
create_temperature_controller_serial_managers()
create_temperature_monitor_serial_manager()
