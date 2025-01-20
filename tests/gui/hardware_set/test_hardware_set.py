"""Tests for the HardwareSet class and associated helper functions."""

from collections.abc import Sequence
from contextlib import nullcontext as does_not_raise
from importlib import resources
from itertools import product
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, call, mock_open, patch

import pytest
import yaml
from frozendict import frozendict
from pubsub import pub
from PySide6.QtWidgets import QMessageBox

from frog.gui.hardware_set.hardware_set import LabelledHardwareSet
from frog.config import HARDWARE_SET_USER_PATH
from frog.device_info import DeviceInstanceRef
from frog.gui.hardware_set import hardware_set
from frog.gui.hardware_set.device import OpenDeviceArgs
from frog.gui.hardware_set.hardware_set import (
    CURRENT_HW_SET_VERSION,
    HardwareSet,
    HardwareSetLoadError,
    _add_hardware_set,
    _device_to_plain_data,
    _get_new_hardware_set_path,
    _hw_set_schema,
    _load_all_hardware_sets,
    _load_builtin_hardware_sets,
    _load_hardware_sets,
    _load_user_hardware_sets,
    _remove_hardware_set,
    get_hardware_sets,
)

FILE_PATH = Path("test/file.yaml")
NAME = "Test hardware set"


def test_subscriptions() -> None:
    """Check the module-level subscriptions."""
    assert pub.isSubscribed(_add_hardware_set, "hardware_set.add")
    assert pub.isSubscribed(_remove_hardware_set, "hardware_set.remove")


@pytest.mark.parametrize(
    "device,expected",
    (
        (
            OpenDeviceArgs(DeviceInstanceRef("base_type"), "my_class"),
            ("base_type", {"class_name": "my_class"}),
        ),
        (
            OpenDeviceArgs(
                DeviceInstanceRef("base_type"), "my_class", frozendict(a=1, b="hello")
            ),
            ("base_type", {"class_name": "my_class", "params": {"a": 1, "b": "hello"}}),
        ),
    ),
)
def test_device_to_plain_data(device: OpenDeviceArgs, expected: dict[str, Any]) -> None:
    """Test _device_to_plain_data()."""
    assert _device_to_plain_data(device) == expected


@patch("frog.gui.hardware_set.hardware_set._device_to_plain_data")
@patch("frog.gui.hardware_set.hardware_set.yaml.dump")
def test_hardware_set_save(dump_mock: Mock, to_plain_mock: Mock) -> None:
    """Test HardwareSet's save() method."""
    file_path = MagicMock()
    devices = (
        OpenDeviceArgs(DeviceInstanceRef(f"base_type{i}"), f"my_class{i}")
        for i in range(2)
    )
    to_plain_mock.side_effect = ((f"key{i}", i) for i in range(2))
    hw_set = HardwareSet(NAME, frozenset(devices), FILE_PATH, False)
    hw_set.save(file_path)
    expected = {
        "version": CURRENT_HW_SET_VERSION,
        "name": NAME,
        "devices": {"key0": 0, "key1": 1},
    }
    assert dump_mock.call_count == 1
    assert dump_mock.mock_calls[0].args[0] == expected


def test_hardware_set_save_and_load(tmp_path: Path) -> None:
    """Test that saved files are loadable."""
    devices = (
        OpenDeviceArgs(DeviceInstanceRef(f"base_type{i}"), f"my_class{i}")
        for i in range(2)
    )
    save_path = tmp_path / "file.yaml"
    hw_set1 = HardwareSet(NAME, frozenset(devices), save_path, False)
    hw_set1.save(save_path)
    hw_set2 = HardwareSet.load(save_path, False)
    assert hw_set1 == hw_set2


@pytest.mark.parametrize(
    "hw_set1,hw_set2",
    (
        # Built-in HardwareSets come before user ones
        (
            HardwareSet("B", frozenset(), Path("b.yaml"), True),
            HardwareSet("A", frozenset(), Path("a.yaml"), False),
        ),
        # Then sort by name
        (
            HardwareSet("A", frozenset(), Path("2.yaml"), True),
            HardwareSet("B", frozenset(), Path("1.yaml"), True),
        ),
        # Lastly, sort by file name
        (
            HardwareSet(NAME, frozenset(), Path("a.yaml"), True),
            HardwareSet(NAME, frozenset(), Path("b.yaml"), True),
        ),
    ),
)
def test_hardware_set_lt(hw_set1: HardwareSet, hw_set2: HardwareSet) -> None:
    """Test HardwareSet's magic __lt__ method()."""
    assert hw_set1 < hw_set2
    assert hw_set2 > hw_set1
    assert hw_set1 != hw_set2


@pytest.mark.parametrize(
    "data,expected",
    (
        # Device given without params
        (
            {
                "name": NAME,
                "devices": {"stepper_motor": {"class_name": "MyStepperMotor"}},
            },
            HardwareSet(
                NAME,
                frozenset((OpenDeviceArgs.create("stepper_motor", "MyStepperMotor"),)),
                FILE_PATH,
                False,
            ),
        ),
        # Device given with params
        (
            {
                "name": NAME,
                "devices": {
                    "stepper_motor": {
                        "class_name": "MyStepperMotor",
                        "params": {"param1": "value1"},
                    }
                },
            },
            HardwareSet(
                NAME,
                frozenset(
                    (
                        OpenDeviceArgs.create(
                            "stepper_motor",
                            "MyStepperMotor",
                            {"param1": "value1"},
                        ),
                    )
                ),
                FILE_PATH,
                False,
            ),
        ),
    ),
)
@patch.object(_hw_set_schema, "validate")
def test_load(validate_mock: Mock, data: dict[str, Any], expected: HardwareSet) -> None:
    """Test HardwareSet's static load() method.

    Validation errors (which should not occur in this test, anyway) are ignored, because
    they are tested elsewhere.
    """
    with patch.object(
        hardware_set.Path,
        "open",
        mock_open(read_data=yaml.dump(data)),
    ):
        result = HardwareSet.load(FILE_PATH, False)
        assert result == expected


@patch.object(_hw_set_schema, "validate")
def test_load_validates_data(validate_mock: Mock) -> None:
    """Check that HardwareSet.load() validates data against the schema."""
    data = {
        "name": NAME,
        "devices": {"stepper_motor": {"class_name": "MyStepperMotor"}},
    }
    with patch.object(
        hardware_set.Path,
        "open",
        mock_open(read_data=yaml.dump(data)),
    ):
        HardwareSet.load(FILE_PATH, False)
        validate_mock.assert_called_once_with(data)


@pytest.mark.parametrize(
    "data,is_valid",
    (
        # Valid, no params
        (
            {
                "version": CURRENT_HW_SET_VERSION,
                "name": NAME,
                "devices": {"stepper_motor": {"class_name": "MyStepperMotor"}},
            },
            True,
        ),
        # Valid, with params
        (
            {
                "version": CURRENT_HW_SET_VERSION,
                "name": NAME,
                "devices": {
                    "stepper_motor": {
                        "class_name": "MyStepperMotor",
                        "params": {"param1": "value1", "param2": 42},
                    }
                },
            },
            True,
        ),
        # Invalid (no name)
        (
            {
                "devices": {"stepper_motor": {"class_name": "MyStepperMotor"}},
            },
            False,
        ),
        # Invalid (name wrong type)
        (
            {
                "name": 42,
                "devices": {"stepper_motor": {"class_name": "MyStepperMotor"}},
            },
            False,
        ),
        # Invalid (no devices)
        (
            {
                "name": NAME,
            },
            False,
        ),
        # Invalid (empty devices)
        (
            {
                "name": NAME,
                "devices": {},
            },
            False,
        ),
        # Invalid (bad key type for device)
        (
            {
                "name": NAME,
                "devices": {42: {"class_name": "MyStepperMotor"}},
            },
            False,
        ),
        # Invalid (bad type for class_name)
        (
            {
                "name": NAME,
                "devices": {"stepper_motor": {"class_name": 42}},
            },
            False,
        ),
        # Invalid (params empty)
        (
            {
                "name": NAME,
                "devices": {
                    "stepper_motor": {
                        "class_name": "MyStepperMotor",
                        "params": {},
                    }
                },
            },
            False,
        ),
        # # Invalid (bad key for params) - currently failing
        # (
        #     {
        #         "name": NAME,
        #         "devices": {
        #             "stepper_motor": {
        #                 "class_name": "MyStepperMotor",
        #                 "params": {3: "value1", "param2": 42},
        #             }
        #         },
        #     },
        #     False,
        # ),
        # Invalid (unexpected extra key)
        (
            {
                "name": NAME,
                "devices": {"stepper_motor": {"class_name": "MyStepperMotor"}},
                "extra_key": 42,
            },
            False,
        ),
    ),
)
def test_schema(data: dict[str, Any], is_valid: bool) -> None:
    """Test that the schema validates correctly."""
    assert _hw_set_schema.is_valid(data) == is_valid


@pytest.mark.parametrize(
    "to_create,expected_file_name",
    (
        ((), "file.yaml"),
        (("file.yaml",), "file_2.yaml"),
        (("file.yaml", "file_2.yaml"), ("file_3.yaml")),
    ),
)
def test_get_new_hardware_set_path(
    to_create: Sequence[str], expected_file_name: str, tmp_path: Path
) -> None:
    """Test _get_new_hardware_set_path()."""
    output_dir = tmp_path / "sub"

    # Create files
    output_dir.mkdir()
    for file_name in to_create:
        open(output_dir / file_name, "w").close()

    assert (
        _get_new_hardware_set_path("file", output_dir)
        == output_dir / expected_file_name
    )


def test_get_new_hardware_set_path_creates_dir(tmp_path: Path) -> None:
    """Test that _get_new_hardware_set_path() creates the target directory."""
    output_dir = tmp_path / "sub"
    _get_new_hardware_set_path("file", output_dir)
    assert output_dir.exists()


@patch("frog.gui.hardware_set.hardware_set._refresh_hardware_set_labels")
@patch("frog.gui.hardware_set.hardware_set._get_new_hardware_set_path")
@patch("frog.gui.hardware_set.hardware_set.show_error_message")
def test_add_hardware_set_success(
    error_message_mock: Mock,
    get_path_mock: Mock,
    refresh_labels_mock: Mock,
    hw_sets: Sequence[HardwareSet],
    sendmsg_mock: MagicMock,
) -> None:
    """Test _add_hardware_set() when it succeeds."""
    in_path = Path("dir1/file.yaml")
    out_path = Path("dir2/file.yaml")
    hw_set = MagicMock()
    hw_set.name = NAME
    hw_set.file_path = in_path
    hw_set.devices = hw_sets[0].devices
    hw_set.built_in = False
    get_path_mock.return_value = out_path
    hw_set_list: list = []
    with patch("frog.gui.hardware_set.hardware_set._hw_sets", hw_set_list):
        hw_set_new = HardwareSet(NAME, hw_sets[0].devices, out_path, built_in=False)
        _add_hardware_set(hw_set)
        get_path_mock.assert_called_once_with(in_path.stem)
        hw_set.save.assert_called_once_with(out_path)
        error_message_mock.assert_not_called()
        refresh_labels_mock.assert_called_once_with()

        # NB: hw_set_list should be sorted but we don't check this
        assert len(hw_set_list) == 1
        assert hw_set_list[0].hw_set == hw_set_new

        sendmsg_mock.assert_called_once_with("hardware_set.added", hw_set=hw_set_new)


@patch("frog.gui.hardware_set.hardware_set._refresh_hardware_set_labels")
@patch("frog.gui.hardware_set.hardware_set._get_new_hardware_set_path")
@patch("frog.gui.hardware_set.hardware_set.show_error_message")
def test_add_hardware_set_fail(
    error_message_mock: Mock,
    get_path_mock: Mock,
    refresh_labels_mock: Mock,
    sendmsg_mock: MagicMock,
) -> None:
    """Test _add_hardware_set() when it fails."""
    in_path = Path("dir1/file.yaml")
    out_path = Path("dir2/file.yaml")
    hw_set = MagicMock()
    hw_set.file_path = in_path
    hw_set.save.side_effect = RuntimeError
    get_path_mock.return_value = out_path
    hw_set_list: list = []
    with patch("frog.gui.hardware_set.hardware_set._hw_sets", hw_set_list):
        _add_hardware_set(hw_set)
        get_path_mock.assert_called_once_with(in_path.stem)
        hw_set.save.assert_called_once_with(out_path)
        error_message_mock.assert_called_once()
        sendmsg_mock.assert_not_called()
        refresh_labels_mock.assert_not_called()


@patch("frog.gui.hardware_set.hardware_set.QFile.moveToTrash")
@patch("frog.gui.hardware_set.hardware_set.QMessageBox")
def test_remove_hardware_set_success(
    msgbox_mock: Mock,
    trash_mock: Mock,
    hw_sets: Sequence[HardwareSet],
    sendmsg_mock: MagicMock,
) -> None:
    """Test _remove_hardware_set() when removal succeeds."""
    msgbox = MagicMock()
    msgbox.exec.return_value = QMessageBox.StandardButton.Yes
    msgbox_mock.StandardButton = QMessageBox.StandardButton
    msgbox_mock.return_value = msgbox
    trash_mock.return_value = True

    hw_set_list = [LabelledHardwareSet(hw_set, hw_set.name) for hw_set in hw_sets]
    with patch("frog.gui.hardware_set.hardware_set._hw_sets", hw_set_list):
        _remove_hardware_set(hw_sets[0])
        assert len(hw_set_list) == 1
        assert hw_set_list[0].hw_set == hw_sets[1]
        trash_mock.assert_called_once_with(str(hw_sets[0].file_path))
        sendmsg_mock.assert_called_once_with("hardware_set.removed")


@patch("frog.gui.hardware_set.hardware_set.QFile.moveToTrash")
@patch("frog.gui.hardware_set.hardware_set.QMessageBox")
def test_remove_hardware_set_cancelled(
    msgbox_mock: Mock,
    trash_mock: Mock,
    hw_sets: Sequence[HardwareSet],
    sendmsg_mock: MagicMock,
) -> None:
    """Test _remove_hardware_set() when the user cancels."""
    msgbox = MagicMock()
    msgbox.exec.return_value = QMessageBox.StandardButton.No
    msgbox_mock.StandardButton = QMessageBox.StandardButton
    msgbox_mock.return_value = msgbox
    trash_mock.return_value = True

    hw_sets = list(hw_sets)
    with patch("frog.gui.hardware_set.hardware_set._hw_sets", hw_sets):
        _remove_hardware_set(hw_sets[0])
        trash_mock.assert_not_called()
        sendmsg_mock.assert_not_called()
        assert hw_sets == list(hw_sets)


@patch("frog.gui.hardware_set.hardware_set.show_error_message")
@patch("frog.gui.hardware_set.hardware_set.QFile.moveToTrash")
@patch("frog.gui.hardware_set.hardware_set.QMessageBox")
def test_remove_hardware_set_fail(
    msgbox_mock: Mock,
    trash_mock: Mock,
    error_mock: Mock,
    sendmsg_mock: MagicMock,
    hw_sets: Sequence[HardwareSet],
) -> None:
    """Test _remove_hardware_set() when deletion fails."""
    msgbox = MagicMock()
    msgbox.exec.return_value = QMessageBox.StandardButton.Yes
    msgbox_mock.StandardButton = QMessageBox.StandardButton
    msgbox_mock.return_value = msgbox
    trash_mock.return_value = False

    hw_sets = list(hw_sets)
    with patch("frog.gui.hardware_set.hardware_set._hw_sets", hw_sets):
        _remove_hardware_set(hw_sets[0])
        trash_mock.assert_called_once_with(str(hw_sets[0].file_path))
        sendmsg_mock.assert_not_called()
        assert hw_sets == list(hw_sets)
        error_mock.assert_called_once()


def test_remove_hardware_set_fail_built_in(hw_sets: Sequence[HardwareSet]) -> None:
    """Test with a built-in hardware set as argument."""
    hw_set = HardwareSet(NAME, hw_sets[0].devices, FILE_PATH, built_in=True)
    with pytest.raises(ValueError):
        _remove_hardware_set(hw_set)


@pytest.mark.parametrize(
    "raise_error,raises",
    (
        (
            errors,
            pytest.raises(HardwareSetLoadError) if any(errors) else does_not_raise(),
        )
        for errors in product((False, True), repeat=2)  # repeat for each hardware set
    ),
)
@patch.object(HardwareSet, "load")
def test_load_hardware_sets(
    load_mock: Mock,
    tmp_path: Path,
    hw_sets: Sequence[HardwareSet],
    raise_error: Sequence[bool],
    raises: Any,
) -> None:
    """Test _load_hardware_sets()."""
    # Create n empty files in tmp_path
    for i in range(len(hw_sets)):
        path = tmp_path / f"file{i}.yaml"
        path.open("w").close()

    i = -1

    def mock_load(*args, **kwargs):
        nonlocal i
        i += 1
        if raise_error[i]:
            raise RuntimeError()
        return hw_sets[i]

    load_mock.side_effect = mock_load
    out: list[HardwareSet] = []
    with raises:
        for hw_set in _load_hardware_sets(tmp_path, built_in=False):
            out.append(hw_set)


@patch.object(HardwareSet, "load")
def test_load_builtin_hardware_sets(load_mock: Mock) -> None:
    """Test the _load_builtin_hardware_sets() function."""
    pkg_path = str(resources.files("frog.gui.hardware_set").joinpath())
    yaml_files = Path(pkg_path).glob("*.yaml")
    list(_load_builtin_hardware_sets())  # assume return value is correct
    load_mock.assert_has_calls([call(file, built_in=True) for file in yaml_files])


def test_builtin_hardware_sets_valid() -> None:
    """Test that the built-in hardware set YAML files are all valid."""
    list(_load_builtin_hardware_sets())


@patch("frog.gui.hardware_set.hardware_set._refresh_hardware_set_labels")
@patch("frog.gui.hardware_set.hardware_set._load_hardware_sets")
def test_load_all_hardware_sets(load_mock: Mock, refresh_labels_mock: Mock) -> None:
    """Test _load_all_hardware_sets()."""
    hw_set_list: list[int] = []
    with patch("frog.gui.hardware_set.hardware_set._hw_sets", hw_set_list):
        load_mock.side_effect = (, (3, 2))  # deliberately unsorted
        _load_all_hardware_sets()
        assert hw_set_list == [0, 1, 2, 3]
        refresh_labels_mock.assert_called_once_with()


@patch("frog.gui.hardware_set.hardware_set._load_hardware_sets")
def test_load_user_hardware_sets_success(load_mock: Mock) -> None:
    """Test _load_user_hardware_sets() when it succeeds."""
    list(_load_user_hardware_sets())  # assume return value is correct
    load_mock.assert_called_once_with(HARDWARE_SET_USER_PATH, built_in=False)


@patch("frog.gui.hardware_set.hardware_set.QFile.moveToTrash")
@patch("frog.gui.hardware_set.hardware_set.QMessageBox")
@patch("frog.gui.hardware_set.hardware_set._load_hardware_sets")
def test_load_user_hardware_sets_no_trash(
    load_mock: Mock, msgbox_mock: Mock, trash_mock: Mock
) -> None:
    """Test _load_user_hardware_sets() when an error occurs and the user cancels."""
    msgbox = MagicMock()
    msgbox_mock.return_value = msgbox
    msgbox_mock.StandardButton = QMessageBox.StandardButton
    msgbox.exec.return_value = QMessageBox.StandardButton.Cancel
    paths = (Path("a.yaml"), Path("b.yaml"))
    load_mock.side_effect = HardwareSetLoadError(paths)
    list(_load_user_hardware_sets())  # assume return value is correct
    load_mock.assert_called_once_with(HARDWARE_SET_USER_PATH, built_in=False)
    trash_mock.assert_not_called()


@pytest.mark.parametrize("trash_succeeded", (True, False))
@patch("frog.gui.hardware_set.hardware_set.logging.error")
@patch("frog.gui.hardware_set.hardware_set.QFile.moveToTrash")
@patch("frog.gui.hardware_set.hardware_set.QMessageBox")
@patch("frog.gui.hardware_set.hardware_set._load_hardware_sets")
def test_load_user_hardware_sets_trash(
    load_mock: Mock,
    msgbox_mock: Mock,
    trash_mock: Mock,
    error_mock: Mock,
    trash_succeeded: bool,
) -> None:
    """Test _load_user_hardware_sets() when an error occurs and the user clicks OK."""
    msgbox = MagicMock()
    msgbox.exec.return_value = QMessageBox.StandardButton.Ok
    msgbox_mock.return_value = msgbox
    msgbox_mock.StandardButton = QMessageBox.StandardButton
    paths = (Path("a.yaml"), Path("b.yaml"))
    load_mock.side_effect = HardwareSetLoadError(paths)
    trash_mock.return_value = trash_succeeded
    list(_load_user_hardware_sets())  # assume return value is correct
    load_mock.assert_called_once_with(HARDWARE_SET_USER_PATH, built_in=False)
    trash_mock.assert_has_calls(tuple(map(call, map(str, paths))))

    # An error message should be printed if trashing files fails
    if trash_succeeded:
        error_mock.assert_not_called()
    else:
        assert error_mock.call_count == len(paths)


@patch("frog.gui.hardware_set.hardware_set._load_all_hardware_sets")
def test_get_hardware_sets(load_mock: Mock, hw_sets: Sequence[HardwareSet]) -> None:
    """Test the get_hardware_sets() method."""
    # Check that _load_hardware_sets() will not be called if hardware sets are already
    # loaded
    # hw_sets = list(range(2))
    hw_set_list = list(hw_sets)
    with patch("frog.gui.hardware_set.hardware_set._hw_sets", hw_set_list):
        ret = list(get_hardware_sets())
        load_mock.assert_not_called()
        assert ret == hw_set_list

    # Check that hardware sets will be loaded if not loaded already
    hw_set_list.clear()
    with patch("frog.gui.hardware_set.hardware_set._hw_sets", hw_set_list):
        ret = list(get_hardware_sets())
        load_mock.assert_called_once_with()
        assert ret == hw_set_list
