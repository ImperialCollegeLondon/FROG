"""Test the DeviceTypeControl class."""

from collections.abc import Sequence
from unittest.mock import MagicMock, Mock, PropertyMock, call, patch

import pytest

from frog.device_info import DeviceInstanceRef, DeviceParameter, DeviceTypeInfo
from frog.gui.hardware_set.device import ConnectionStatus
from frog.gui.hardware_set.device_view import (
    DeviceParametersWidget,
    DeviceTypeControl,
)

DEVICE_TYPES = [
    DeviceTypeInfo("my_class1", "Device 1"),
    DeviceTypeInfo("my_class2", "Device 2"),
]


@pytest.fixture
def widget(subscribe_mock: MagicMock, qtbot) -> DeviceTypeControl:
    """Create a DeviceTypeControl fixture."""
    # Patch only while the control is constructed, so setup doesn't touch a real
    # settings file: neither loading saved parameter values nor reading the
    # previously-opened device type.
    with (
        patch("frog.gui.hardware_set.device_view.load_saved_parameter_values"),
        patch("frog.gui.hardware_set.device_view.get_setting") as get_setting_mock,
    ):
        get_setting_mock.return_value = None
        return DeviceTypeControl(
            "Device type", DeviceInstanceRef("base_type"), DEVICE_TYPES
        )


@pytest.mark.parametrize(
    "active_device,device_status,previous_device,expected_device",
    (
        (active, state, previous, active or default)
        for previous, default in (
            (None, DEVICE_TYPES[0]),
            (DEVICE_TYPES[1], DEVICE_TYPES[1]),
        )
        for active, state in (
            (None, ConnectionStatus.DISCONNECTED),
            (DEVICE_TYPES[0], ConnectionStatus.CONNECTING),
            (DEVICE_TYPES[0], ConnectionStatus.CONNECTED),
        )
    ),
)
@patch(
    "frog.gui.hardware_set.device_view."
    "DeviceParametersWidget.load_saved_parameter_values"
)
@patch(
    "frog.gui.hardware_set.device_view.DeviceTypeControl._update_open_btn_enabled_state"
)
@patch("frog.gui.hardware_set.device_view.get_setting")
def test_init(
    get_setting_mock: Mock,
    update_btn_mock: Mock,
    load_saved_mock: Mock,
    active_device: DeviceTypeInfo | None,
    device_status: ConnectionStatus,
    previous_device: DeviceTypeInfo | None,
    expected_device: DeviceTypeInfo,
    subscribe_mock: MagicMock,
    qtbot,
) -> None:
    """Test the constructor."""
    instance = DeviceInstanceRef("base_type")

    get_setting_mock.return_value = (
        previous_device.class_name if previous_device else None
    )
    widget = DeviceTypeControl(
        "Base type",
        instance,
        DEVICE_TYPES,
        active_device_type=active_device.class_name if active_device else None,
        device_status=device_status,
    )
    assert widget._device_instance is instance
    items = [
        widget._device_combo.itemText(i) for i in range(widget._device_combo.count())
    ]
    assert items == [t.description for t in DEVICE_TYPES]
    assert [w.device_type for w in widget._device_widgets] == DEVICE_TYPES

    assert widget._device_combo.currentText() == expected_device.description

    if (
        device_status != ConnectionStatus.DISCONNECTED
        and active_device.class_name == expected_device.class_name  # type: ignore[union-attr]
    ):
        assert widget._open_close_btn.text() == "Close"
    else:
        assert widget._open_close_btn.text() == "Open"

    update_btn_mock.assert_called_once_with()

    subscribe_mock.assert_has_calls(
        [
            call(widget._on_device_open_end, f"device.after_opening.{instance!s}"),
            call(widget._on_device_closed, f"device.closed.{instance!s}"),
        ]
    )

    assert len(list(widget.findChildren(DeviceParametersWidget))) == 1


def test_init_no_device_types(qtbot) -> None:
    """Test that the constructor raises an exception when no device types specified."""
    with pytest.raises(ValueError):
        DeviceTypeControl("Device type", DeviceInstanceRef("base_type"), [])


@pytest.mark.parametrize(
    "status", (ConnectionStatus.CONNECTING, ConnectionStatus.CONNECTED)
)
def test_set_device_status_active(
    status: ConnectionStatus, widget: DeviceTypeControl
) -> None:
    """Test the _set_device_status() method for connecting and connected devices."""
    with patch.object(widget._status_control, "set_status") as set_status_mock:
        with patch.object(widget, "_set_combos_enabled") as combos_mock:
            with patch.object(widget._open_close_btn, "setText") as set_btn_text_mock:
                widget._set_device_status(status)
                set_status_mock.assert_called_once_with(status)
                combos_mock.assert_called_once_with(False)
                set_btn_text_mock("Close")


def test_set_device_status_disconnected(widget: DeviceTypeControl) -> None:
    """Test the _set_device_status() method for disconnected devices."""
    with patch.object(widget._status_control, "set_status") as set_status_mock:
        with patch.object(widget, "_set_combos_enabled") as combos_mock:
            with patch.object(widget._open_close_btn, "setText") as set_btn_text_mock:
                widget._set_device_status(ConnectionStatus.DISCONNECTED)
                set_status_mock.assert_called_once_with(ConnectionStatus.DISCONNECTED)
                combos_mock.assert_called_once_with(True)
                set_btn_text_mock("Open")


@pytest.mark.parametrize(
    "params,expected_enabled",
    (
        ({"param_not_poss": DeviceParameter("", ())}, False),
        (
            {"param_poss": DeviceParameter("", range(2))},
            True,
        ),
        (
            {
                "param_not_poss": DeviceParameter("", ()),
                "param_poss": DeviceParameter("", range(2)),
            },
            False,
        ),
        (
            {
                "param_poss1": DeviceParameter("", range(2)),
                "param_poss2": DeviceParameter("", range(2)),
            },
            True,
        ),
    ),
)
@patch(
    "frog.gui.hardware_set.device_view.DeviceTypeControl.current_device_type_widget",
    new_callable=PropertyMock,
)
def test_update_open_btn_enabled_state(
    widget_mock: Mock,
    params: Sequence[DeviceParameter],
    expected_enabled: bool,
    widget: DeviceTypeControl,
    qtbot,
) -> None:
    """Test the _update_open_btn_enabled_state() method.

    The open/close button should be disabled if there are no possible values for at
    least one parameter and enabled otherwise.
    """
    widget_mock.device_type.parameters = params
    with patch.object(widget, "_open_close_btn") as btn_mock:
        widget._update_open_btn_enabled_state()
        btn_mock.setEnabled(expected_enabled)


def test_change_device_type(widget: DeviceTypeControl, qtbot) -> None:
    """Test that changing the selected device type causes the GUI to update."""
    with patch.object(widget, "_update_open_btn_enabled_state") as update_btn_mock:
        assert widget.layout().itemAt(1).widget() is widget._device_widgets[0]  # type: ignore[union-attr]
        widget._device_combo.setCurrentIndex(1)
        assert widget.layout().itemAt(1).widget() is widget._device_widgets[1]  # type: ignore[union-attr]
        assert widget._device_widgets[0].isHidden()
        assert not widget._device_widgets[1].isHidden()
        update_btn_mock.assert_called_once_with()


@pytest.mark.parametrize("enable", (True, False))
@patch(
    "frog.gui.hardware_set.device_view.DeviceTypeControl.current_device_type_widget",
    new_callable=PropertyMock,
)
def test_set_combos_enabled(
    widget_mock: Mock, enable: bool, widget: DeviceTypeControl, qtbot
) -> None:
    """Test the _set_combos_enabled() method."""
    device_widget = MagicMock()
    widget_mock.return_value = device_widget
    with patch.object(widget, "_device_combo") as combo_mock:
        widget._set_combos_enabled(enable)
        combo_mock.setEnabled.assert_called_once_with(enable)
        device_widget.setEnabled.assert_called_once_with(enable)


def test_select_device(widget: DeviceTypeControl, qtbot) -> None:
    """Test the _select_device() method."""
    with patch.object(
        widget._device_widgets[1], "load_saved_parameter_values"
    ) as load_params_mock:
        assert widget._device_combo.currentIndex() == 0
        widget._select_device(DEVICE_TYPES[1].class_name)
        assert widget._device_combo.currentIndex() == 1
        load_params_mock.assert_called_once_with()


@patch("frog.gui.hardware_set.device_view.logging.warn")
def test_select_device_unknown_device(
    warn_mock: Mock, widget: DeviceTypeControl, qtbot
) -> None:
    """Test the _select_device() method with an unknown device."""
    assert widget._device_combo.currentIndex() == 0
    widget._select_device("made_up_class")
    assert widget._device_combo.currentIndex() == 0
    warn_mock.assert_called_once()


@patch("frog.gui.hardware_set.device_view.open_device")
def test_open_device(open_device_mock: Mock, widget: DeviceTypeControl, qtbot) -> None:
    """Test the _open_device() method."""
    widget._open_device()
    open_device_mock.assert_called_once_with(
        DEVICE_TYPES[0].class_name,
        widget._device_instance,
        widget._device_widgets[0].current_parameter_values,
    )


@patch("frog.gui.hardware_set.device_view.show_error_message")
@patch(
    "frog.gui.hardware_set.device_view.DeviceParametersWidget.current_parameter_values",
    new_callable=PropertyMock,
)
def test_open_device_bad_params(
    get_params_mock: Mock, error_message_mock: Mock, widget: DeviceTypeControl, qtbot
) -> None:
    """Test that a dialog is shown when parameter values are invalid."""
    get_params_mock.side_effect = ValueError
    widget._open_device()
    error_message_mock.assert_called_once()


@patch("frog.gui.hardware_set.device_view.close_device")
def test_close_device(
    close_device_mock: Mock, widget: DeviceTypeControl, qtbot
) -> None:
    """Test the _close_device() method."""
    widget._close_device()
    close_device_mock.assert_called_once_with(widget._device_instance)


def test_on_device_open_start(widget: DeviceTypeControl, qtbot) -> None:
    """Test the _on_device_open_start() method."""
    with patch.object(widget, "_select_device") as select_mock:
        with patch.object(widget, "_set_device_status") as set_status_mock:
            widget._on_device_open_start(
                DeviceInstanceRef("base_type"), "some_class", {}
            )
            select_mock.assert_called_once_with("some_class")
            set_status_mock(ConnectionStatus.CONNECTING)


def test_on_device_open_end(widget: DeviceTypeControl, qtbot) -> None:
    """Test the _on_device_open_end() method."""
    with patch.object(widget, "_select_device") as select_mock:
        with patch.object(widget, "_set_device_status") as set_status_mock:
            widget._on_device_open_end(DeviceInstanceRef("base_type"), "some_class")
            select_mock.assert_called_once_with("some_class")
            set_status_mock(ConnectionStatus.CONNECTED)


def test_on_device_closed(widget: DeviceTypeControl, qtbot) -> None:
    """Test the _on_device_closed() method."""
    with patch.object(widget, "_set_device_status") as set_status_mock:
        widget._on_device_closed(DeviceInstanceRef("base_type"))
        set_status_mock(ConnectionStatus.DISCONNECTED)


def test_open_close_btn(widget: DeviceTypeControl, qtbot) -> None:
    """Test the open/close button works."""
    with patch.object(widget, "_open_device") as open_mock:
        with patch.object(widget, "_close_device") as close_mock:
            assert widget._open_close_btn.text() == "Open"
            widget._open_close_btn.click()
            open_mock.assert_called_once_with()
            close_mock.assert_not_called()

            open_mock.reset_mock()
            widget._open_close_btn.setText("Close")
            widget._open_close_btn.click()
            open_mock.assert_not_called()
            close_mock.assert_called_once_with()
