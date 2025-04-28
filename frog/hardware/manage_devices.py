"""This module contains code for interfacing with different hardware devices."""

import logging
from collections.abc import Mapping
from importlib import import_module
from typing import Any, TypeVar, cast

from pubsub import pub

from frog.device_info import DeviceInstanceRef
from frog.hardware.device import Device, get_device_types
from frog.hardware.plugins import __name__ as _plugins_name

_devices: dict[DeviceInstanceRef, Device] = {}

_T = TypeVar("_T", bound=Device)


def get_device_instance(base_type: type[_T], name: str | None = None) -> _T | None:
    """Get the instance of the device of type base_type with an optional name.

    If there is no device matching these parameters, None is returned.
    """
    key = DeviceInstanceRef(base_type.get_device_base_type_info().name, name)

    try:
        return cast(_T, _devices[key])
    except KeyError:
        return None


def _open_device(
    instance: DeviceInstanceRef, class_name: str, params: Mapping[str, Any]
) -> None:
    """Open the specified device type.

    Args:
        instance: The instance that this device will be when opened
        class_name: The name of the device type's class
        params: Device parameters
    """
    module, _, class_name_part = f"{_plugins_name}.{class_name}".rpartition(".")

    # Assume this is safe because the class and module will not be provided directly by
    # the user
    cls: type[Device] = getattr(import_module(module), class_name_part)

    logging.info(f"Opening device of type {instance.base_type}: {class_name_part}")

    if device := _devices.get(instance):
        logging.warn(f"Replacing existing instance of device of type {instance!s}")
        _try_close_device(device)

    # If this instance also has a name (e.g. "hot_bb") then we also need to pass this as
    # an argument
    params_with_name = dict(params)
    if instance.name:
        params_with_name["name"] = instance.name

    pub.sendMessage(
        f"device.before_opening.{instance!s}",
        instance=instance,
        class_name=class_name,
        params=params,
    )
    try:
        _devices[instance] = cls(**params_with_name)
    except Exception as error:
        logging.error(f"Failed to open {instance!s} device: {error!s}")
        pub.sendMessage(f"device.error.{instance!s}", instance=instance, error=error)
        pub.sendMessage(f"device.closed.{instance!s}", instance=instance)


def _try_close_device(device: Device) -> None:
    """Try to close a device and send a message on success.

    If an exception is raised it is logged without being re-raised.
    """
    logging.info(f"Closing device of type {device.__class__.__name__}")

    try:
        device.close()
    except Exception as ex:
        logging.warn(f"Error while closing {device.__class__.__name__}: {ex!s}")

    instance = device.get_instance_ref()
    pub.sendMessage(f"device.closed.{instance!s}", instance=instance)


def _close_device(instance: DeviceInstanceRef) -> None:
    """Close the device referred to by instance."""
    try:
        _try_close_device(_devices.pop(instance))
    except KeyError:
        # There is no instance of this type of device, so do nothing
        pass


def _on_device_error(instance: DeviceInstanceRef, error: Exception) -> None:
    """Treat all errors as fatal on device error."""
    _close_device(instance)


def _close_all_devices() -> None:
    """Attempt to close all devices, ignoring errors."""
    for device in _devices.values():
        _try_close_device(device)
    _devices.clear()


def _broadcast_device_types() -> None:
    """Broadcast the available device types via pubsub."""
    pub.sendMessage("device.list.response", device_types=get_device_types())


pub.subscribe(_open_device, "device.open")
pub.subscribe(_close_device, "device.close")
pub.subscribe(_on_device_error, "device.error")
pub.subscribe(_broadcast_device_types, "device.list.request")

pub.subscribe(_close_all_devices, "window.closed")
