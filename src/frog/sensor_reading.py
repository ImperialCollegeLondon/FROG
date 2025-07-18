"""Provides a class for representing physical quantities monitored by sensors."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class SensorReading:
    """Class for representing physical quantities monitored by sensors.

    Args:
        name: human-readable name of the physical quantity
        value: value of the physical quantity
        unit: unit in which the value is presented
    """

    name: str
    value: Decimal | float
    unit: str

    def __str__(self) -> str:
        """Print a property's name, value and unit in a readable format.

        Returns:
            str: The name, value and unit of a property.
        """
        return f"{self.name} = {self.value:.6f} {self.unit}"

    def val_str(self) -> str:
        """Print a property's value and unit in required format.

        Returns:
            str: The value and unit of a property
        """
        return f"{self.value:.6f} {self.unit}"
