"""Test the DeviceControl class."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from frog.device_info import DeviceBaseTypeInfo, DeviceInstanceRef, DeviceTypeInfo
from frog.gui.hardware_set.device import ConnectionStatus, OpenDeviceArgs
from frog.gui.hardware_set.device_view import DeviceControl

CONNECTED_DEVICES = (
    OpenDeviceArgs.create("stepper_motor", "MyStepperMotor"),
    OpenDeviceArgs.create(
        "temperature_monitor",
        "MyTemperatureMonitor",
        {"param1": "value1"},
    ),
)


@pytest.fixture
def widget(sendmsg_mock: MagicMock, subscribe_mock: Mock, qtbot) -> DeviceControl:
    """Return a DeviceControl fixture."""
    device_manager = MagicMock()
    device_manager.get_connected_devices.return_value = CONNECTED_DEVICES
    return DeviceControl(device_manager)


def test_init(sendmsg_mock: MagicMock, subscribe_mock: MagicMock, qtbot) -> None:
    """Test the constructor."""
    device_manager = MagicMock()
    widget = DeviceControl(device_manager)
    assert widget._device_manager is device_manager

    # Check that the list of devices was requested and the response is listened for
    subscribe_mock.assert_called_once_with(
        widget._on_device_list, "device.list.response"
    )
    sendmsg_mock.assert_called_once_with("device.list.request")


@pytest.mark.parametrize(
    "instance,expected",
    (
        (DeviceInstanceRef("stepper_motor"), CONNECTED_DEVICES[0].class_name),
        (DeviceInstanceRef("made_up"), None),
    ),
)
def test_get_connected_device(
    instance: DeviceInstanceRef, expected: str | None, widget: DeviceControl, qtbot
) -> None:
    """Test the _get_connected_device() method."""
    assert widget._get_connected_device(instance) == expected


@patch("frog.gui.hardware_set.device_view.DeviceTypeControl")
def test_on_device_list(widget_mock: Mock, widget: DeviceControl, qtbot) -> None:
    """Test the _on_device_list() method."""
    base_type = DeviceBaseTypeInfo("base_type", "Base type", (), ())
    device_types = [
        DeviceTypeInfo("my_class1", "Device 1"),
        DeviceTypeInfo("my_class2", "Device 2"),
    ]

    with patch.object(widget, "layout"):
        with patch.object(widget, "_get_connected_device") as connected_mock:
            connected_mock.return_value = "connected_device"
            widget._on_device_list({base_type: device_types})

            # In practice, there will be more than one base type, but let's just test
            # that the code creates this one widget for ease
            widget_mock.assert_called_once_with(
                "Base type",
                DeviceInstanceRef("base_type"),
                device_types,
                "connected_device",
                ConnectionStatus.CONNECTED,
            )
