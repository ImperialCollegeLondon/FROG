"""This module provides an interface to a dummy EM27 monitor."""

from importlib import resources
from pathlib import Path

from frog.hardware.plugins.sensors.em27_sensors import EM27SensorsBase


class DummyEM27Sensors(EM27SensorsBase, description="Dummy EM27 sensors"):
    """A dummy device for EM27 sensors."""

    def __init__(self) -> None:
        """Create a new EM27 property monitor."""
        dummy_em27_fp = resources.files("frog.hardware.plugins.sensors").joinpath(
            "diag_autom.htm"
        )
        super().__init__(Path(str(dummy_em27_fp)).as_uri())
