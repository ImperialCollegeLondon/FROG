"""Helper functions for managing connections to devices."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from frozendict import frozendict
from pubsub import pub
from PySide6.QtCore import QObject, Signal

from frog.device_info import DeviceInstanceRef
from frog.gui.error_message import show_error_message


@dataclass(frozen=True)
class OpenDeviceArgs:
    """Arguments needed to open a device."""

    instance: DeviceInstanceRef
    class_name: str
    params: frozendict[str, Any] = field(default_factory=frozendict)

    def open(self) -> None:
        """Open the device."""
        open_device(self.class_name, self.instance, self.params)

    def close(self) -> None:
        """Close the device."""
        close_device(self.instance)

    @classmethod
    def create(
        cls, instance: str, class_name: str, params: Mapping[str, Any] = frozendict()
    ) -> OpenDeviceArgs:
        """Create an OpenDeviceArgs using basic types."""
        return cls(DeviceInstanceRef.from_str(instance), class_name, frozendict(params))


@dataclass
class ActiveDeviceProperties:
    """The properties of a device that is connecting or connected."""

    args: OpenDeviceArgs
    """Arguments used to open the device."""
    state: ConnectionStatus
    """Whether the device is connecting or connected."""

    def __post_init__(self) -> None:
        """Check whether user attempted to create for a disconnected device."""
        if self.state == ConnectionStatus.DISCONNECTED:
            raise ValueError(
                "Cannot create ActiveDeviceProperties for disconnected device"
            )


class ConnectionStatus(Enum):
    """The connection state of a device."""

    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2


def open_device(
    class_name: str, instance: DeviceInstanceRef, params: Mapping[str, Any]
) -> None:
    """Open a connection to a device."""
    pub.sendMessage(
        "device.open", class_name=class_name, instance=instance, params=params
    )


def close_device(instance: DeviceInstanceRef) -> None:
    """Close a connection to a device."""
    pub.sendMessage("device.close", instance=instance)


class ActiveDeviceManager(QObject):
    """A class used by the frontend to monitor and control backend devices."""

    device_opened = Signal(DeviceInstanceRef, str)
    device_started_open = Signal(DeviceInstanceRef, str, Mapping)
    device_closed = Signal(DeviceInstanceRef)

    def __init__(
        self,
        active_devices: dict[DeviceInstanceRef, ActiveDeviceProperties] | None = None,
    ) -> None:
        """Create a new _ActiveDeviceManager."""
        super().__init__()
        self._active_devices = active_devices or {}
        pub.subscribe(self._on_device_open_start, "device.before_opening")
        pub.subscribe(self._on_device_open_end, "device.after_opening")
        pub.subscribe(self._on_device_closed, "device.closed")
        pub.subscribe(self._on_device_error, "device.error")

    def get_connected_devices(self) -> Iterable[OpenDeviceArgs]:
        """Get active devices which are connected (not connecting)."""
        return (
            props.args
            for props in self._active_devices.values()
            if props.state == ConnectionStatus.CONNECTED
        )

    def get_active_devices(self) -> Mapping[DeviceInstanceRef, ActiveDeviceProperties]:
        """Get the current active devices."""
        return self._active_devices

    def disconnect_all(self) -> None:
        """Disconnect from all devices."""
        # We need to make a copy because keys will be removed as we close devices
        for device in list(self._active_devices.keys()):
            pub.sendMessage("device.close", instance=device)

    def _on_device_open_start(
        self, instance: DeviceInstanceRef, class_name: str, params: Mapping[str, Any]
    ) -> None:
        """Store device open parameters and update GUI."""
        args = OpenDeviceArgs(instance, class_name, frozendict(params))
        dev_props = ActiveDeviceProperties(args, ConnectionStatus.CONNECTING)
        self._active_devices[instance] = dev_props
        self.device_started_open.emit(instance, class_name, params)

    def _on_device_open_end(self, instance: DeviceInstanceRef, class_name: str) -> None:
        """Add instance to _connected_devices and update GUI."""
        dev_props = self._active_devices[instance]
        dev_props.state = ConnectionStatus.CONNECTED
        assert dev_props.args.class_name == class_name
        self.device_opened.emit(instance, class_name)

    def _on_device_closed(self, instance: DeviceInstanceRef) -> None:
        """Remove instance from _connected devices and update GUI."""
        try:
            # Remove the device matching this instance type (there should be only one)
            del self._active_devices[instance]
        except KeyError:
            # No device of this type found
            pass
        else:
            self.device_closed.emit(instance)

    def _on_device_error(
        self, instance: DeviceInstanceRef, error: BaseException
    ) -> None:
        """Show an error message when something has gone wrong with the device.

        Todo:
            The name of the device isn't currently very human readable.
        """
        show_error_message(
            None,
            f"A fatal error has occurred with the {instance!s} device: {error!s}",
            title="Device error",
        )
