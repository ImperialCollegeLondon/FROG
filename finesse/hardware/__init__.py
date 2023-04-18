"""This module contains code for interfacing with different hardware devices."""
import sys

from pubsub import pub

if "--dummy-em27" in sys.argv:
    from .dummy_em27_scraper import DummyEM27Scraper as EM27Scraper
    from .opus.dummy import DummyOPUSInterface as OPUSInterface
else:
    from .em27_scraper import EM27Scraper  # type: ignore
    from .opus.em27 import OPUSInterface  # type: ignore

from . import data_file_writer  # noqa
from .stepper_motor import create_stepper_motor_serial_manager
from .temperature import (
    create_temperature_controller_serial_managers,
    create_temperature_monitor_serial_manager,
)

opus: OPUSInterface


def _init_hardware():
    global opus

    opus = OPUSInterface()


def _stop_hardware():
    global opus
    del opus


pub.subscribe(_init_hardware, "window.opened")
pub.subscribe(_stop_hardware, "window.closed")

scraper = EM27Scraper()
create_stepper_motor_serial_manager()
create_temperature_controller_serial_managers()
create_temperature_monitor_serial_manager()
