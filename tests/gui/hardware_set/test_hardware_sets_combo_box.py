"""Tests for the HardwareSetsComboBox class."""

from collections.abc import Sequence
from pathlib import Path
from unittest.mock import MagicMock, Mock, PropertyMock, call, patch

import pytest

from frog.gui.hardware_set.device import OpenDeviceArgs
from frog.gui.hardware_set.hardware_set import HardwareSet
from frog.gui.hardware_set.hardware_sets_combo_box import HardwareSetsComboBox


@pytest.fixture
@patch("frog.gui.hardware_set.hardware_sets_combo_box.get_hardware_sets")
def combo(
    get_hw_sets_mock: Mock, hw_sets: Sequence[HardwareSet], qtbot
) -> HardwareSetsComboBox:
    """A fixture for a combo box containing multiple hardware sets."""
    get_hw_sets_mock.return_value = hw_sets
    return HardwareSetsComboBox()


@patch.object(HardwareSetsComboBox, "current_hardware_set", new_callable=PropertyMock)
def test_on_hardware_set_added(
    cur_hw_set_mock: PropertyMock,
    combo: HardwareSetsComboBox,
    hw_sets: Sequence[HardwareSet],
    qtbot,
) -> None:
    """Test the _on_hardware_set_added() method."""
    # combo = HardwareSetsComboBox()
    with patch.object(combo, "_load_hardware_set_list") as load_mock:
        combo._on_hardware_set_added(hw_sets[1])
        load_mock.assert_called_once_with()
        cur_hw_set_mock.assert_called_once_with(hw_sets[1])


@patch("frog.gui.hardware_set.hardware_sets_combo_box.get_hardware_sets")
def test_load_hardware_set_list(
    get_hw_sets_mock: Mock, combo: HardwareSetsComboBox, qtbot
) -> None:
    """Test the _load_hardware_set_list() method."""
    get_hw_sets_mock.return_value = range(2)
    with patch.object(combo, "_add_hardware_set") as add_mock:
        combo._load_hardware_set_list()
        add_mock.assert_has_calls((call(0), call(1)))


_HW_SET = HardwareSet(
    "Test 1",
    frozenset(
        (
            OpenDeviceArgs.create("stepper_motor", "MyStepperMotor"),
            OpenDeviceArgs.create(
                "temperature_monitor",
                "MyTemperatureMonitor",
                {"param1": "value1"},
            ),
        )
    ),
    Path("path/test.yaml"),
    False,
)


# @pytest.mark.parametrize(
#     "existing_hw_sets,hw_set_name,expected_name,built_in",
#     (
#         ((), _HW_SET.name, _HW_SET.name, False),
#         ((_HW_SET,), _HW_SET.name, f"{_HW_SET.name} (2)", False),
#         ((_HW_SET, _HW_SET), _HW_SET.name, f"{_HW_SET.name} (3)", False),
#         ((), _HW_SET.name, f"{_HW_SET.name} (built in)", True),
#         ((_HW_SET,), _HW_SET.name, f"{_HW_SET.name} (built in) (2)", True),
#         (
#             (_HW_SET, _HW_SET),
#             _HW_SET.name,
#             f"{_HW_SET.name} (built in) (3)",
#             True,
#         ),
#     ),
# )
# def test_add_hardware_set(
#     existing_hw_sets: Sequence[HardwareSet],
#     hw_set_name: str,
#     expected_name: str,
#     built_in: bool,
#     combo: HardwareSetsComboBox,
#     qtbot,
# ) -> None:
#     """Test the _add_hardware_set() method."""
#     combo.clear()
#     for hw_set in existing_hw_sets:
#         hw_set = HardwareSet(hw_set.name, hw_set.devices, hw_set.file_path, built_in)
#         combo._add_hardware_set(hw_set)

#     with patch.object(combo, "addItem") as add_mock:
#         hw_set = HardwareSet(hw_set_name, frozenset(), Path(), built_in)
#         combo._add_hardware_set(hw_set)
#         add_mock.assert_called_once_with(expected_name, hw_set)


def test_add_hardware_set(
    hw_set_name: str,
    built_in: bool,
    combo: HardwareSetsComboBox,
    qtbot,
) -> None:
    """Test the _add_hardware_set() method."""
    with patch.object(combo, "addItem") as add_mock:
        combo._add_hardware_set("some label", _HW_SET)
        add_mock.assert_called_once_with("some label", _HW_SET)


def test_get_current_hardware_set(combo: HardwareSetsComboBox, qtbot) -> None:
    """Test getting the current_hardware_set property."""
    hw_set = MagicMock()
    with patch.object(combo, "currentData", return_value=hw_set):
        assert combo.current_hardware_set == hw_set


def test_set_current_hardware_set(
    combo: HardwareSetsComboBox, hw_sets: Sequence[HardwareSet], qtbot
) -> None:
    """Test setting the current_hardware_set property."""
    assert combo.currentIndex() == 0
    combo.current_hardware_set = hw_sets[1]
    assert combo.currentIndex() == 1


def test_set_current_hardware_set_error(combo: HardwareSetsComboBox, qtbot) -> None:
    """Test that current_hardware_set's setter raises an error if does not exist."""
    with pytest.raises(ValueError):
        combo.current_hardware_set = MagicMock()


@patch.object(HardwareSetsComboBox, "current_hardware_set", new_callable=PropertyMock)
def test_get_current_hardware_set_devices(
    cur_hw_set_mock: PropertyMock, combo: HardwareSetsComboBox, qtbot
) -> None:
    """Test the current_hardware_set_devices property."""
    # Check that it returns hw_set.devices for a valid hardware set
    hw_set = MagicMock()
    cur_hw_set_mock.return_value = hw_set
    assert combo.current_hardware_set_devices == hw_set.devices

    # Check that it returns an empty frozenset if no hardware set is selected
    cur_hw_set_mock.reset_mock()
    cur_hw_set_mock.return_value = None
    assert combo.current_hardware_set_devices == frozenset()
