"""Common constants used throughout the app."""
from importlib.metadata import version
from pathlib import Path

APP_NAME = "FINESSE"
"""A human-readable name for the app."""

APP_AUTHOR = "Imperial College London"
"""The name of the app's author (used for program data path)."""

APP_VERSION = version("finesse")
"""The current version of the app."""

ANGLE_PRESETS = {
    "zenith": 180.0,
    "nadir": 0.0,
    "hot_bb": 270.0,
    "cold_bb": 225.0,
    "home": 0.0,
    "park": 90.0,
}
"""Preset angles that the mirror can rotate to."""

BAUDRATES = (4800, 9600, 19200, 38400, 57600, 115200)
"""The valid baud rates for use by the GUI."""

NUM_TEMPERATURE_MONITOR_CHANNELS = 8
"""The number of temperature channels for temperature monitors."""

DUMMY_DEVICE_PORT = "Dummy"
"""The port name to display for dummy serial devices."""

DEFAULT_SCRIPT_PATH = Path.home()
"""The default path to search for script files in."""

DEFAULT_DATA_FILE_PATH = Path.home()
"""The default path to save data files."""

EM27_URL = "http://10.10.0.1/diag_autom.htm"
"""The URL of the EM27 monitoring web server."""

EM27_PROPERTY_POLL_INTERVAL = 2.0
"""Poll rate for EM27 properties."""

STEPPER_MOTOR_TOPIC = "stepper_motor"
"""The topic name to use for stepper motor-related messages."""

DEFAULT_ST10_BAUDRATE = 9600
"""The default baudrate to use for the ST10 controller."""

TEMPERATURE_MONITOR_TOPIC = "temperature_monitor"
"""The topic name to use for temperature monitor-related messages."""

DEFAULT_DP9800_BAUDRATE = 38400
"""The default baudrate to use for DP9800 temperature monitors."""

TEMPERATURE_CONTROLLER_TOPIC = "temperature_controller"
"""The topic name to use for temperature controller-related messages."""

DEFAULT_TC4820_BAUDRATE = 115200
"""The default baudrate to use for TC4820 temperature controllers."""

OPUS_IP = "10.10.0.2"
"""The IP address of the machine running the OPUS software."""

ALLOW_DUMMY_DEVICES = True
"""Whether to allow the user to choose dummy serial devices."""

TEMPERATURE_MONITOR_POLL_INTERVAL = 2
"""Number of seconds between temperature monitoring device reads."""

TEMPERATURE_PLOT_TIME_RANGE = 900
"""Range of time axis on blackbody temperature plot, in seconds."""
