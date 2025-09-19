"""Test the ActiveDeviceManager class."""

from unittest.mock import MagicMock, Mock, patch

import pytest
from frozendict import frozendict

from frog.device_info import DeviceInstanceRef
from frog.gui.hardware_set.device import (
    ActiveDeviceManager,
    ActiveDeviceProperties,
    ConnectionStatus,
    OpenDeviceArgs,
)


@pytest.fixture
def sample_device_args() -> OpenDeviceArgs:
    """Create sample OpenDeviceArgs for testing."""
    return OpenDeviceArgs(
        instance=DeviceInstanceRef("test_base_type", "test_name"),
        class_name="TestDevice",
        params=frozendict({"param1": "value1", "param2": 42}),
    )


@pytest.fixture
def sample_device_properties(
    sample_device_args: OpenDeviceArgs,
) -> ActiveDeviceProperties:
    """Create sample ActiveDeviceProperties for testing."""
    return ActiveDeviceProperties(
        args=sample_device_args,
        state=ConnectionStatus.CONNECTED,
    )


@pytest.fixture
def active_devices_dict(
    sample_device_properties: ActiveDeviceProperties,
) -> dict[DeviceInstanceRef, ActiveDeviceProperties]:
    """Create a sample active devices dictionary for testing."""
    return {sample_device_properties.args.instance: sample_device_properties}


def test_init_empty(subscribe_mock: MagicMock, qtbot) -> None:
    """Test initialization with no active devices."""
    manager = ActiveDeviceManager()

    assert manager._active_devices == {}
    assert len(manager.devices) == 0
    assert list(manager.connected_devices) == []

    # Verify all required subscriptions
    expected_calls = [
        ("device.before_opening", manager._on_device_open_start),
        ("device.after_opening", manager._on_device_open_end),
        ("device.closed", manager._on_device_closed),
        ("device.error", manager._on_device_error),
    ]

    for topic, callback in expected_calls:
        subscribe_mock.assert_any_call(callback, topic)

    assert subscribe_mock.call_count == 4


def test_init_with_active_devices(
    active_devices_dict: dict[DeviceInstanceRef, ActiveDeviceProperties],
    subscribe_mock: MagicMock,
    qtbot,
) -> None:
    """Test initialization with pre-existing active devices."""
    manager = ActiveDeviceManager(active_devices_dict)

    assert manager._active_devices is active_devices_dict
    assert len(manager.devices) == 1
    expected_device = next(iter(active_devices_dict.values())).args
    assert list(manager.connected_devices) == [expected_device]


def test_devices_property(
    active_devices_dict: dict[DeviceInstanceRef, ActiveDeviceProperties],
    subscribe_mock: MagicMock,
    qtbot,
) -> None:
    """Test the devices property returns the correct mapping."""
    manager = ActiveDeviceManager(active_devices_dict)
    devices = manager.devices

    assert devices == active_devices_dict
    # Ensure it's a mapping, not the actual dict for encapsulation
    assert type(devices) is dict


def test_connected_devices_property_empty(subscribe_mock: MagicMock, qtbot) -> None:
    """Test connected_devices property when no devices are connected."""
    manager = ActiveDeviceManager()
    connected = list(manager.connected_devices)

    assert connected == []


def test_connected_devices_property_mixed_states(
    sample_device_args: OpenDeviceArgs,
    subscribe_mock: MagicMock,
    qtbot,
) -> None:
    """Test connected_devices property filters out connecting devices."""
    connecting_device = ActiveDeviceProperties(
        args=OpenDeviceArgs(
            instance=DeviceInstanceRef("connecting_type"),
            class_name="ConnectingDevice",
            params=frozendict(),
        ),
        state=ConnectionStatus.CONNECTING,
    )

    connected_device = ActiveDeviceProperties(
        args=sample_device_args,
        state=ConnectionStatus.CONNECTED,
    )

    active_devices = {
        connecting_device.args.instance: connecting_device,
        connected_device.args.instance: connected_device,
    }

    manager = ActiveDeviceManager(active_devices)
    connected = list(manager.connected_devices)

    assert len(connected) == 1
    assert connected[0] == sample_device_args


def test_on_device_open_start(subscribe_mock: MagicMock, qtbot) -> None:
    """Test _on_device_open_start method."""
    manager = ActiveDeviceManager()

    instance = DeviceInstanceRef("test_type", "test_name")
    class_name = "TestDevice"
    params = {"param1": "value1"}

    with qtbot.waitSignal(manager.device_started_open) as blocker:
        manager._on_device_open_start(instance, class_name, params)

    # Check signal emission
    assert blocker.args == [instance, class_name, params]

    # Check internal state
    assert instance in manager._active_devices
    device_props = manager._active_devices[instance]
    assert device_props.args.instance == instance
    assert device_props.args.class_name == class_name
    assert device_props.args.params == frozendict(params)
    assert device_props.state == ConnectionStatus.CONNECTING


def test_on_device_open_end(
    sample_device_properties: ActiveDeviceProperties,
    subscribe_mock: MagicMock,
    qtbot,
) -> None:
    """Test _on_device_open_end method."""
    # Start with a connecting device
    connecting_props = ActiveDeviceProperties(
        args=sample_device_properties.args,
        state=ConnectionStatus.CONNECTING,
    )
    active_devices = {sample_device_properties.args.instance: connecting_props}
    manager = ActiveDeviceManager(active_devices)

    instance = sample_device_properties.args.instance
    class_name = sample_device_properties.args.class_name

    with qtbot.waitSignal(manager.device_opened) as blocker:
        manager._on_device_open_end(instance, class_name)

    # Check signal emission
    assert blocker.args == [instance, class_name]

    # Check state change
    device_props = manager._active_devices[instance]
    assert device_props.state == ConnectionStatus.CONNECTED


def test_on_device_closed_existing_device(
    active_devices_dict: dict[DeviceInstanceRef, ActiveDeviceProperties],
    subscribe_mock: MagicMock,
    qtbot,
) -> None:
    """Test _on_device_closed method with an existing device."""
    manager = ActiveDeviceManager(active_devices_dict)
    instance = next(iter(active_devices_dict.keys()))

    with qtbot.waitSignal(manager.device_closed) as blocker:
        manager._on_device_closed(instance)

    # Check signal emission
    assert blocker.args == [instance]

    # Check device removal
    assert instance not in manager._active_devices
    assert len(manager._active_devices) == 0


def test_on_device_closed_nonexistent_device(subscribe_mock: MagicMock, qtbot) -> None:
    """Test _on_device_closed method with a non-existent device."""
    manager = ActiveDeviceManager()
    instance = DeviceInstanceRef("nonexistent_type")

    # Should not emit signal for non-existent device
    with patch.object(manager, "device_closed") as signal_mock:
        manager._on_device_closed(instance)
        signal_mock.emit.assert_not_called()


def test_disconnect_all_empty(
    subscribe_mock: MagicMock, sendmsg_mock: MagicMock, qtbot
) -> None:
    """Test disconnect_all method with no active devices."""
    manager = ActiveDeviceManager()
    manager.disconnect_all()

    sendmsg_mock.assert_not_called()


def test_disconnect_all_with_devices(
    active_devices_dict: dict[DeviceInstanceRef, ActiveDeviceProperties],
    subscribe_mock: MagicMock,
    sendmsg_mock: MagicMock,
    qtbot,
) -> None:
    """Test disconnect_all method with active devices."""
    # Add another device for better testing
    instance2 = DeviceInstanceRef("test_type_2")
    device_props2 = ActiveDeviceProperties(
        args=OpenDeviceArgs(instance2, "TestDevice2", frozendict()),
        state=ConnectionStatus.CONNECTED,
    )
    active_devices_dict[instance2] = device_props2

    manager = ActiveDeviceManager(active_devices_dict)
    manager.disconnect_all()

    # Should send close message for each device
    assert sendmsg_mock.call_count == 2
    for instance in active_devices_dict.keys():
        sendmsg_mock.assert_any_call("device.close", instance=instance)


@patch("frog.gui.hardware_set.device.show_error_message")
def test_on_device_error(
    show_error_mock: Mock,
    subscribe_mock: MagicMock,
    qtbot,
) -> None:
    """Test _on_device_error method."""
    manager = ActiveDeviceManager()
    instance = DeviceInstanceRef("test_type", "test_name")
    error = Exception("Test error message")

    manager._on_device_error(instance, error)

    # Check error message display
    show_error_mock.assert_called_once_with(
        None,
        f"A fatal error has occurred with the {instance!s} device: {error!s}",
        title="Device error",
    )


def test_signal_connections(subscribe_mock: MagicMock, qtbot) -> None:
    """Test that all Qt signals are properly defined."""
    manager = ActiveDeviceManager()

    # Check that signals exist and are Signal objects
    assert hasattr(manager, "device_opened")
    assert hasattr(manager, "device_started_open")
    assert hasattr(manager, "device_closed")

    # Signals should be accessible and of correct type
    from PySide6.QtCore import Signal

    assert isinstance(type(manager).device_opened, type(Signal()))
    assert isinstance(type(manager).device_started_open, type(Signal()))
    assert isinstance(type(manager).device_closed, type(Signal()))
