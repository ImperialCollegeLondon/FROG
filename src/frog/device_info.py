"""Provides common dataclasses about devices for using in backend and frontend."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast


@dataclass
class DeviceParameter:
    """A parameter that a device needs (e.g. baudrate)."""

    description: str
    """A human-readable description of the parameter."""
    possible_values: Sequence | type
    """Possible values the parameter can take.

    This can either be a Sequence of possible values or a type (e.g. str or float).
    """
    default_value: Any = None
    """The default value for this parameter.

    A value of None indicates that there is no default value."""

    def __post_init__(self) -> None:
        """Check that default value is valid."""
        if self.default_value is None:
            return

        if isinstance(self.possible_values, Sequence):
            if self.default_value not in self.possible_values:
                raise RuntimeError(
                    f"Default value of {self.default_value} not in possible values"
                )
        elif not isinstance(self.default_value, cast(type, self.possible_values)):
            raise RuntimeError("Default value doesn't match type of possible values")


@dataclass
class DeviceTypeInfo:
    """Description of a device."""

    class_name: str
    """The name of the device's class including the module name."""
    description: str
    """A human-readable name for the device."""
    parameters: Mapping[str, DeviceParameter] = field(default_factory=dict)
    """The device parameters."""


@dataclass(frozen=True)
class DeviceBaseTypeInfo:
    """A generic device type (e.g. stepper motor)."""

    name: str
    """Short name for use in pubsub topics etc."""
    description: str
    """A human-readable name for these types of device."""
    names_short: Sequence[str]
    """A list of possible names for this type of device."""
    names_long: Sequence[str]
    """A list of names for this type of device (human readable)."""

    def get_instances_and_descriptions(self) -> Iterable[tuple[DeviceInstanceRef, str]]:
        """Get instances and descriptions.

        If there are no possible names for the type, then there will only be one
        instance, otherwise there will be one per name.
        """
        if not self.names_long:
            yield DeviceInstanceRef(self.name), self.description
            return

        for short, long in zip(self.names_short, self.names_long):
            instance = DeviceInstanceRef(self.name, short)
            yield instance, f"{self.description} ({long})"


@dataclass(frozen=True)
class DeviceInstanceRef:
    """Information uniquely describing an instance of a particular device type."""

    base_type: str
    """The device base type."""
    name: str | None = None
    """The (optional) name of the device.

    Used for disambiguating devices where there can be multiple instances.
    """

    def __str__(self) -> str:
        """Get the short string representation of this device."""
        s = self.base_type
        if self.name:
            s += f".{self.name}"
        return s

    @staticmethod
    def from_str(s: str) -> DeviceInstanceRef:
        """Convert from a string in the format "base_type.name" or "base_type"."""
        base_type, _, name = s.partition(".")
        return DeviceInstanceRef(base_type, name or None)
