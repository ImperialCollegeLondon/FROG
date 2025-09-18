"""Tests for device.py."""

from abc import abstractmethod
from collections.abc import Callable, Sequence
from typing import Any, ClassVar
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from frog.device_info import DeviceParameter
from frog.hardware.device import (
    AbstractDevice,
    Device,
    DeviceTypeInfo,
    get_device_types,
)
from frog.hardware.plugins import __name__ as plugins_name

MOCK_DEVICE_TOPIC = "mock"


# For some reason, mypy isn't happy with the kwargs for the classes below
# mypy: disable-error-code=call-arg
class _MockBaseClass(Device, name=MOCK_DEVICE_TOPIC, description="Mock base class"):
    pass


class _MockDevice(_MockBaseClass, description="Mock device"):
    def signal_is_opened(self):
        """Make this a no-op to simplify testing."""
        self._is_open = True


class _NamedMockBaseClass(
    Device,
    name=MOCK_DEVICE_TOPIC,
    description="Mock base class with device names",
    names_short=("name1", "name2"),
    names_long=("First device", "Second device"),
):
    pass


class _NamedMockDevice(_NamedMockBaseClass, description="Mock device with name"):
    pass


@pytest.fixture
def device():
    """A fixture for a mock device."""
    return _MockDevice()


@patch("frog.hardware.device.load_all_plugins")
def test_get_device_types(load_plugins_mock: Mock) -> None:
    """Test the get_device_types() function."""
    # NB: Deliberately not in alphabetical order as the result should be sorted
    base_type_names = ("BaseTypeB", "BaseTypeA")
    base_types_info = []
    base_types = []
    for desc in base_type_names:
        info_mock = MagicMock()
        info_mock.description = desc
        base_types_info.append(info_mock)
        type_mock = MagicMock()
        type_mock.get_device_base_type_info.return_value = info_mock
        base_types.append(type_mock)

    # As above, this is a set in the actual implementation
    device_types_info = []
    device_types = []
    for i, base_type_info in enumerate([*base_types_info, base_types_info[0]]):
        # As above, we want to check that the device types are sorted by name
        info_mock = MagicMock()
        info_mock.description = f"Device{len(base_types) - i}"
        device_types_info.append(info_mock)

        device_mock = MagicMock()
        device_mock.get_device_base_type_info.return_value = base_type_info
        device_mock.get_device_type_info.return_value = info_mock
        device_types.append(device_mock)

    with patch("frog.hardware.device._base_types", base_types):
        with patch("frog.hardware.device._device_types", device_types):
            device_types_out = get_device_types()
            load_plugins_mock.assert_called_once_with()

            keys = list(device_types_out.keys())

            # Check that keys are present and sorted
            assert [key.description for key in keys] == [
                "BaseTypeA",
                "BaseTypeB",
            ]

            def get_names(idx):
                return [t.description for t in device_types_out[keys[idx]]]

            # Check that device types are all present and sorted by name
            assert get_names(0) == ["Device1"]
            assert get_names(1) == ["Device0", "Device2"]


def test_abstract_device_add_parameters_description_only() -> None:
    """Test adding a device parameter with only a description provided."""

    class MyDevice(AbstractDevice, parameters={"my_param": "My parameter"}):
        def __init__(self, my_param: int) -> None:
            pass

    assert MyDevice.get_device_parameters() == {
        "my_param": DeviceParameter("My parameter", int)
    }


def test_abstract_device_add_parameters_possible_values() -> None:
    """Test adding a device parameter with description and possible values provided."""

    class MyDevice(AbstractDevice, parameters={"my_param": ("My parameter", range(2))}):
        def __init__(self, my_param: int) -> None:
            pass

    assert MyDevice.get_device_parameters() == {
        "my_param": DeviceParameter("My parameter", range(2))
    }


def test_abstract_device_add_parameters_missing_arg() -> None:
    """Test that an error is raised for a missing parameter."""
    with pytest.raises(ValueError):

        class MyDevice(AbstractDevice, parameters={"my_param": "My parameter"}):
            pass


def test_abstract_device_add_parameters_bad_type() -> None:
    """Test that a TypeError is raised for a bad parameter type."""
    with pytest.raises(TypeError):

        class MyDevice(AbstractDevice, parameters={"my_param": 42}):  # type: ignore
            def __init__(self, my_param: int) -> None:
                pass


def test_abstract_device_default_value() -> None:
    """Test that default values for parameters are set correctly."""

    class MyDevice(AbstractDevice, parameters={"my_param": "My parameter"}):
        def __init__(self, my_param: int = 42) -> None:
            pass

    # Default value (and type) should be set from __init__'s signature
    assert MyDevice.get_device_parameters() == {
        "my_param": DeviceParameter("My parameter", int, 42)
    }

    class MyDeviceSubclass(MyDevice):
        def __init__(self, my_param: int = 43) -> None:
            pass

    # Default value should be different for this subclass
    assert MyDeviceSubclass.get_device_parameters() == {
        "my_param": DeviceParameter("My parameter", int, 43)
    }


def test_abstract_device_get_device_base_type_info() -> None:
    """Test the get_device_base_type_info() classmethod."""

    class MyDevice(AbstractDevice):
        _device_base_type_info = "INFO"  # type: ignore

    assert MyDevice.get_device_base_type_info() == "INFO"


def test_abstract_device_get_device_type_info() -> None:
    """Test the get_device_type_info() classmethod."""
    description = "Some description"
    module = "some_module"

    class MyDevice(AbstractDevice):
        __module__ = f"{plugins_name}.{module}"  # pretend module is in plugins dir
        _device_base_type_info = "INFO"  # type: ignore
        _device_description = description
        _device_parameters: ClassVar[dict[str, DeviceParameter]] = {}

    assert MyDevice.get_device_type_info() == DeviceTypeInfo(
        f"{module}.MyDevice", description, {}
    )


def _wrapped_func_error_test(device: Device, wrapper: Callable, *args) -> None:
    has_run = False

    def raise_error():
        nonlocal has_run
        has_run = True
        raise RuntimeError()

    with patch.object(device, "send_error_message") as error_mock:
        wrapped_func = wrapper(raise_error, *args)
        wrapped_func()
        assert has_run
        error_mock.assert_called_once()


def test_device_pubsub_errors_success(device: Device) -> None:
    """Test Device's pubsub_errors() method when no exception is raised."""
    has_run = False

    def noop():
        nonlocal has_run
        has_run = True

    with patch.object(device, "send_error_message") as error_mock:
        wrapped_func = device.pubsub_errors(noop)
        wrapped_func()
        assert has_run
        error_mock.assert_not_called()


def test_device_pubsub_errors_fail(device: Device) -> None:
    """Test Device's pubsub_errors() method when an exception is raised."""
    _wrapped_func_error_test(device, device.pubsub_errors)


@pytest.mark.parametrize(
    "return_val,kwarg_names,forwarded_args",
    (
        (None, (), ()),
        (
            0,
            ("value",),
            (0,),
        ),
        ((0, 1), ("val1", "val2"), (0, 1)),
    ),
)
def test_device_pubsub_broadcast_success(
    device: Device,
    sendmsg_mock: MagicMock,
    return_val: Any,
    kwarg_names: Sequence[str],
    forwarded_args: Sequence[Any],
) -> None:
    """Test Device's pubsub_broadcast() method."""
    has_run = False

    def noop():
        nonlocal has_run
        has_run = True
        return return_val

    with patch.object(device, "send_error_message") as error_mock:
        wrapped_func = device.pubsub_broadcast(noop, "success", *kwarg_names)
        wrapped_func()
        assert has_run
        sendmsg_mock.assert_called_once_with(
            "device.mock.success", **dict(zip(kwarg_names, forwarded_args))
        )
        error_mock.assert_not_called()


def test_device_pubsub_broadcast_fail(device: Device) -> None:
    """Test Device's pubsub_broadcast() method when an exception is raised."""
    _wrapped_func_error_test(device, device.pubsub_broadcast, "success")


def test_device_send_error_message(device: Device, sendmsg_mock: MagicMock) -> None:
    """Test Device's send_error_message() method."""
    error = RuntimeError()
    device.send_error_message(error)
    sendmsg_mock.assert_called_once_with(
        "device.error.mock", instance=device.get_instance_ref(), error=error
    )


def _device_subscribe_test(
    device: Device, subscribe_mock: MagicMock, wrapper_name: str, *args
) -> None:
    assert len(device._subscriptions) == 0

    def noop():
        pass

    with patch.object(device, wrapper_name) as wrapper_mock:
        wrapped = MagicMock()
        wrapper_mock.return_value = wrapped
        device.subscribe(noop, "message", *args)
        wrapper_mock.assert_called_once_with(noop, *args)
        sub_args = (wrapped, "device.mock.message")
        assert device._subscriptions == [sub_args]
        subscribe_mock.assert_called_once_with(*sub_args)


def test_device_subscribe_errors_only(
    device: Device, subscribe_mock: MagicMock
) -> None:
    """Test the subscribe() method for when a message is only sent in case of error."""
    _device_subscribe_test(device, subscribe_mock, "pubsub_errors")


def test_device_subscribe_broadcast(device: Device, subscribe_mock: MagicMock) -> None:
    """Test the subscribe() method with a message sent for error and success."""
    _device_subscribe_test(device, subscribe_mock, "pubsub_broadcast", "suffix", "name")


def test_device_ignored_class():
    """Test that it is possible to create a class not saved to a device registry."""
    with patch.object(Device, "_init_base_type") as init_base_mock:
        with patch.object(Device, "_init_device_type") as init_device_mock:

            class IgnoredMockClass(_MockBaseClass):
                @abstractmethod
                def some_method(self):
                    pass

            init_base_mock.assert_not_called()
            init_device_mock.assert_not_called()


def test_device_init() -> None:
    """Test Device's constructor when no name is provided."""
    with patch.object(_MockDevice, "signal_is_opened") as signal_mock:
        device = _MockDevice()
        assert device.topic == f"device.{MOCK_DEVICE_TOPIC}"
        assert device.name is None
        signal_mock.assert_called_once_with()


def test_device_init_async() -> None:
    """Test Device's constructor for devices with async open."""

    class _MockDeviceAsync(
        _MockBaseClass, description="Mock device with async open", async_open=True
    ):
        pass

    assert _MockDeviceAsync._device_async_open

    with patch.object(_MockDevice, "signal_is_opened") as signal_mock:
        device = _MockDeviceAsync()
        assert device.topic == f"device.{MOCK_DEVICE_TOPIC}"
        assert device.name is None
        signal_mock.assert_not_called()


def test_device_init_unexpected_name() -> None:
    """Test Device's constructor when an unexpected name is provided.

    Only device types whose base types define names_short and names_long can select a
    name.
    """
    with pytest.raises(RuntimeError):
        _MockDevice("name1")


def test_device_init_with_name() -> None:
    """Test Device's constructor when a name is provided."""
    device = _NamedMockDevice("name1")
    assert device.topic == f"device.{MOCK_DEVICE_TOPIC}.name1"
    assert device.name == "name1"


def test_device_init_with_invalid_name() -> None:
    """Test Device's constructor when an invalid name is provided."""
    with pytest.raises(RuntimeError):
        _NamedMockDevice("name3")


def test_device_init_missing_name():
    """Test Device's constructor when a name should be provided but isn't."""
    with pytest.raises(RuntimeError):
        _NamedMockDevice()


def test_device_signal_is_opened(
    device: Device, subscribe_mock: MagicMock, sendmsg_mock: MagicMock
) -> None:
    """Test the signal_is_opened() method."""
    class_name = "my_class_name"
    type_info = DeviceTypeInfo(class_name, "Class description", {})

    # We need to patch the class name as classes outside the plugin dir are disallowed
    with patch.object(device, "get_device_type_info", return_value=type_info):
        device._is_open = False
        assert not device._subscriptions
        func1 = MagicMock()
        func2 = MagicMock()
        subscriptions = [(func1, "topic1"), (func2, "topic2")]
        device._subscriptions = subscriptions.copy()  # type: ignore

        # Call Device's member function directly because we've patched it out for
        # _MockDevice
        Device.signal_is_opened(device)
        instance = device.get_instance_ref()
        class_name = device.get_device_type_info().class_name

    subscribe_mock.assert_has_calls([call(*args) for args in subscriptions])

    sendmsg_mock.assert_has_calls(
        [
            call(
                f"device.after_opening.{instance!s}",
                instance=instance,
                class_name=class_name,
            ),
            call(f"device.opened.{instance!s}"),
        ]
    )


def test_device_signal_is_opened_fail_already_open(
    device: Device, sendmsg_mock: MagicMock
) -> None:
    """Test the signal_is_opened() method fails if already open."""
    class_name = "my_class_name"
    type_info = DeviceTypeInfo(class_name, "Class description", {})

    # We need to patch the class name as classes outside the plugin dir are disallowed
    with patch.object(device, "get_device_type_info", return_value=type_info):
        device._is_open = True

        with pytest.raises(Exception):
            # Call Device's member function directly because we've patched it out for
            # _MockDevice
            Device.signal_is_opened(device)


def test_device_close(device: Device, unsubscribe_mock: MagicMock) -> None:
    """Test the close() method."""
    func = MagicMock()
    my_topic = "topic"
    device._subscriptions.append((func, my_topic))
    device.close()
    assert unsubscribe_mock.call_count == 1
    unsubscribe_mock.assert_called_once_with(func, my_topic)
