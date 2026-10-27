"""Tests for the DeviceParametersWidget class."""

from collections.abc import Mapping
from unittest.mock import Mock, patch

import pytest

from frog.device_info import DeviceParameter, DeviceTypeInfo
from frog.gui.hardware_set.device_view import (
    ComboParameterWidget,
    DeviceParametersWidget,
    TextParameterWidget,
)


@pytest.fixture
def widget(qtbot) -> DeviceParametersWidget:
    """A fixture providing a DeviceParametersWidget."""
    # Patch only while the widget is constructed, so the constructor doesn't load
    # real saved values. The real function is restored for the test body.
    with patch("frog.gui.hardware_set.device_view.load_saved_parameter_values"):
        return DeviceParametersWidget(
            DeviceTypeInfo(
                "my_class",
                "My Device",
                {
                    "param1": DeviceParameter("Parameter 1", range(2)),
                    "param2": DeviceParameter("Parameter 2", int, 0),
                },
            )
        )


def test_combo_parameter_widget(qtbot) -> None:
    """Test the ComboParameterWidget class."""
    widget = ComboParameterWidget(range(2))
    assert all(i == widget.itemData(i) for i in range(2))

    assert widget.currentIndex() == 0
    assert widget.value == 0
    widget.value = 1
    assert widget.currentIndex() == 1
    assert widget.value == 1


def test_text_parameter_widget(qtbot) -> None:
    """Test the TextParameterWidget class."""
    widget = TextParameterWidget(int)
    assert widget.text() == ""
    widget.value = 0
    assert widget.text() == "0"
    assert widget.value == 0
    widget.value = 1
    assert widget.text() == "1"
    assert widget.value == 1

    widget.setText("non integer")
    with pytest.raises(ValueError):
        widget.value


@pytest.mark.parametrize(
    "params",
    (
        # no params
        {},
        # one param
        {"my_param": DeviceParameter("", ("value1", "value2"))},
        # two params
        {
            "param1": DeviceParameter("", ("value1", "value2"), "value1"),
            "param2": DeviceParameter("", int),
        },
    ),
)
def test_init(params: Mapping[str, DeviceParameter], qtbot) -> None:
    """Test the constructor."""
    device_type = DeviceTypeInfo("my_class", "My Device", params)

    with patch.object(
        DeviceParametersWidget, "load_saved_parameter_values"
    ) as load_params_mock:
        widget = DeviceParametersWidget(device_type)
        assert widget.device_type is device_type
        load_params_mock.assert_called_once_with()

    assert widget._param_widgets.keys() == params.keys()
    for name, param in params.items():
        param_widget = widget._param_widgets[name]
        if param.default_value:
            assert param_widget.value == param.default_value


@pytest.mark.parametrize("param_name", ("param1", "param2"))
@patch("frog.gui.hardware_set.device_view.settings")
def test_load_saved_parameter_values(
    settings_mock: Mock, param_name: str, widget: DeviceParametersWidget, qtbot
) -> None:
    """Test the load_saved_parameter_values() method."""
    settings_mock.value.return_value = {param_name: 1}
    assert widget._param_widgets[param_name].value == 0
    widget.load_saved_parameter_values()
    assert widget._param_widgets[param_name].value == 1


@pytest.mark.parametrize("param_name", ("param1", "param2"))
@patch("frog.gui.hardware_set.device_view.settings")
def test_load_saved_parameter_values_none_saved(
    settings_mock: Mock, param_name: str, widget: DeviceParametersWidget, qtbot
) -> None:
    """Test the load_saved_parameter_values() method if there are no values saved."""
    settings_mock.value.return_value = None
    assert widget._param_widgets[param_name].value == 0
    widget.load_saved_parameter_values()
    assert widget._param_widgets[param_name].value == 0


@patch("frog.gui.hardware_set.device_view.settings")
@patch("frog.gui.hardware_set.device_view.logging.warn")
def test_load_saved_parameter_values_error(
    warn_mock: Mock,
    settings_mock: Mock,
    widget: DeviceParametersWidget,
    qtbot,
) -> None:
    """Test the load_saved_parameter_values() method ignores errors."""
    settings_mock.value.return_value = {"made_up": 1}
    widget.load_saved_parameter_values()
    warn_mock.assert_called_once()


def test_current_parameter_values(widget: DeviceParametersWidget, qtbot) -> None:
    """Test the current_parameter_values property."""
    assert widget.current_parameter_values == {"param1": 0, "param2": 0}
