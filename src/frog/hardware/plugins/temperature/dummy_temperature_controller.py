"""Provides a dummy TC4820 device."""

from __future__ import annotations

from decimal import Decimal

from frog.hardware.noise_producer import NoiseParameters, NoiseProducer
from frog.hardware.plugins.temperature.temperature_controller_base import (
    TemperatureControllerBase,
)


class DummyTemperatureController(
    TemperatureControllerBase, description="Dummy temperature controller"
):
    """A dummy temperature controller device which produces random noise."""

    def __init__(
        self,
        name: str,
        temperature_params: NoiseParameters = NoiseParameters(35.0, 0.1),
        power_params: NoiseParameters = NoiseParameters(40.0, 2.0),
        alarm_status: int = 0,
        initial_set_point: Decimal = Decimal(70),
    ) -> None:
        """Create a new DummyTemperatureController.

        Args:
            name: The name of the device, to distinguish it from others
            temperature_params: The parameters for temperature's NoiseProducer
            power_params: The parameters for power's NoiseProducer
            alarm_status: The value of the alarm status used forever (0 is no error)
            initial_set_point: What the temperature set point is initially
        """
        self._temperature_producer = NoiseProducer.from_parameters(
            temperature_params, type=Decimal
        )
        self._power_producer = NoiseProducer.from_parameters(power_params, type=int)
        self._alarm_status = alarm_status
        self._set_point = initial_set_point

        super().__init__(name)

    @property
    def temperature(self) -> Decimal:
        """The current temperature reported by the device."""
        return self._temperature_producer()

    @property
    def power(self) -> int:
        """The current power output of the device."""
        return self._power_producer()

    @property
    def alarm_status(self) -> int:
        """The current error status of the system.

        A value of zero indicates that no error has occurred.
        """
        return self._alarm_status

    @property
    def set_point(self) -> Decimal:
        """The set point temperature (in degrees).

        In other words, this indicates the temperature the device is aiming towards.
        """
        return self._set_point

    @set_point.setter
    def set_point(self, temperature: Decimal) -> None:
        self._set_point = temperature
