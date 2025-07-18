"""The HardwareSet dataclass and associated helper functions."""

from __future__ import annotations

import bisect
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from pubsub import pub
from PySide6.QtCore import QFile
from PySide6.QtWidgets import QMessageBox
from schema import And, Const, Optional, Schema

from frog.config import HARDWARE_SET_USER_PATH
from frog.gui.error_message import show_error_message
from frog.gui.hardware_set.device import OpenDeviceArgs

CURRENT_HW_SET_VERSION = 1
"""The current version of the hardware set schema."""


def _device_to_plain_data(device: OpenDeviceArgs) -> tuple[str, dict[str, Any]]:
    """Get a representation of the device using basic data types.

    Used for serialisation.
    """
    out_dict: dict[str, Any] = dict(class_name=device.class_name)

    # Only add params key if there are parameters
    if device.params:
        out_dict["params"] = dict(device.params)

    return str(device.instance), out_dict


class HardwareSetLoadError(Exception):
    """An exception raised when one or more hardware sets fails to load."""

    def __init__(self, file_paths: Sequence[Path]) -> None:
        """Create a new HardwareSetLoadError.

        Args:
            file_paths: The paths of files which failed to load
        """
        super().__init__(
            f"Failed to load the following files: {', '.join(map(str, file_paths))}"
        )
        self.file_paths = file_paths


def _non_empty(x: Any) -> bool:
    return bool(x)


_hw_set_schema = Schema(
    {
        "version": Const(
            CURRENT_HW_SET_VERSION, f"Version number must be {CURRENT_HW_SET_VERSION}"
        ),
        "name": str,
        "devices": And(
            _non_empty,
            {
                str: {
                    "class_name": str,
                    Optional("params"): And(_non_empty, dict[str, Any]),
                }
            },
        ),
    }
)
"""Schema for validating hardware set config files."""


@dataclass(frozen=True)
class HardwareSet:
    """Represents a collection of devices for a particular hardware configuration."""

    name: str
    devices: frozenset[OpenDeviceArgs]
    file_path: Path
    built_in: bool

    def __lt__(self, other: HardwareSet) -> bool:
        """Used for sorting HardwareSets.

        Built-in hardware sets come before custom ones, then the hardware sets are
        sorted by name. In the case that two hardware sets have the same name, they will
        be distinguished by file path (which should be unique).

        The GUI appends numbers to distinguish hardware sets with the same names. The
        reason for also using the file path for sorting is because it is not guaranteed
        that hardware set config files will always be loaded in the same order and we
        don't want the name + number pairs to change between runs of FROG.
        """
        return (not self.built_in, self.name, self.file_path) < (
            not other.built_in,
            other.name,
            other.file_path,
        )

    def save(self, file_path: Path) -> None:
        """Save this hardware set as a YAML file."""
        with file_path.open("w") as file:
            devices = dict(map(_device_to_plain_data, self.devices))
            data = dict(version=CURRENT_HW_SET_VERSION, name=self.name, devices=devices)
            yaml.dump(data, file, sort_keys=False)

    @classmethod
    def load(cls, file_path: Path, built_in: bool = False) -> HardwareSet:
        """Load a HardwareSet from a YAML file."""
        logging.info(f"Loading hardware set from {file_path}")

        with file_path.open() as file:
            plain_data: dict[str, Any] = yaml.safe_load(file)

        # Check that loaded data matches schema
        _hw_set_schema.validate(plain_data)

        devices = frozenset(
            OpenDeviceArgs.create(k, **v)
            for k, v in plain_data.get("devices", {}).items()
        )
        return cls(plain_data["name"], devices, file_path, built_in)


def _get_new_hardware_set_path(
    stem: str, output_dir: Path = HARDWARE_SET_USER_PATH
) -> Path:
    """Get a new valid path for a hardware set.

    If the containing directory does not exist, it will be created.

    Args:
        stem: The root of the filename, minus the extension
        output_dir: The output directory
    """
    file_name = f"{stem}.yaml"
    file_path = output_dir / file_name
    i = 2
    while file_path.exists():
        file_name = f"{stem}_{i}.yaml"
        file_path = output_dir / file_name
        i += 1

    output_dir.mkdir(exist_ok=True)
    return file_path


def _add_hardware_set(hw_set: HardwareSet) -> None:
    """Save a hardware set to disk and add to in-memory store."""
    file_path = _get_new_hardware_set_path(hw_set.file_path.stem)
    logging.info(f"Copying hardware set from {hw_set.file_path} to {file_path}")
    try:
        hw_set.save(file_path)
    except Exception as error:
        show_error_message(
            None, f"Error saving file to {file_path}: {error!s}", "Could not save file"
        )
    else:
        # We need to create a new object because the file path has changed
        new_hw_set = HardwareSet(hw_set.name, hw_set.devices, file_path, built_in=False)

        # Insert into store, keeping it sorted
        bisect.insort(_hw_sets, new_hw_set)

        # Signal that a new hardware set has been added
        pub.sendMessage("hardware_set.added", hw_set=new_hw_set)


def _remove_hardware_set(hw_set: HardwareSet) -> None:
    """Remove a hardware set after confirming with the user.

    If the user confirms, the associated config file will be moved to the recycle bin.
    """
    if hw_set.built_in:
        raise ValueError("Cannot remove built-in hardware set")

    msgbox = QMessageBox(
        QMessageBox.Icon.Question,
        "Remove hardware set",
        f'Are you sure you want to remove the hardware set "{hw_set.name}"? '
        "It will be moved to the recycle bin.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if msgbox.exec() == QMessageBox.StandardButton.Yes:
        if QFile.moveToTrash(str(hw_set.file_path)):
            _hw_sets.remove(hw_set)
            pub.sendMessage("hardware_set.removed")
        else:
            show_error_message(None, "Failed to delete hardware set", "Deletion failed")


def _load_hardware_sets(dir: Path, built_in: bool) -> Iterable[HardwareSet]:
    """Load hardware sets from the specified directory.

    Raises:
        HardwareSetLoadError: If one or more files failed to load
    """
    failed_files: list[Path] = []
    for path in dir.glob("*.yaml"):
        try:
            yield HardwareSet.load(path, built_in=built_in)
        except Exception as error:
            logging.error(f"Could not load file {path}: {error!s}")
            failed_files.append(path)

    # Only raise an error after yielding as many HardwareSets as will load
    if failed_files:
        raise HardwareSetLoadError(failed_files)


def _load_builtin_hardware_sets() -> Iterable[HardwareSet]:
    """Load all the default hardware sets included with FROG."""
    pkg_path = str(resources.files("frog.gui.hardware_set").joinpath())

    # In theory, this may raise an error, but let's assume that all the built-in configs
    # are in the correct format
    yield from _load_hardware_sets(Path(pkg_path), built_in=True)


def _load_user_hardware_sets() -> Iterable[HardwareSet]:
    """Load hardware sets added by the user."""
    try:
        yield from _load_hardware_sets(HARDWARE_SET_USER_PATH, built_in=False)
    except HardwareSetLoadError as error:
        # Give the user the option of deleting malformed files
        joined_paths = "\n - ".join(path.name for path in error.file_paths)
        msg_box = QMessageBox(
            QMessageBox.Icon.Critical,
            "Failed to load hardware sets",
            f"Failed to load the following hardware sets:\n\n - {joined_paths}\n\n"
            "Would you like to move them to the recycle bin?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        )
        ret = msg_box.exec()
        if ret != QMessageBox.StandardButton.Ok:
            return

        for path in error.file_paths:
            if QFile.moveToTrash(str(path)):
                logging.info(f"Trashed {path}")
            else:
                logging.error(f"Failed to trash {path}")


def _load_all_hardware_sets() -> None:
    """Load all known hardware sets from disk."""
    global _hw_sets
    _hw_sets.extend(_load_builtin_hardware_sets())
    _hw_sets.extend(_load_user_hardware_sets())
    _hw_sets.sort()


def get_hardware_sets() -> Iterable[HardwareSet]:
    """Get all hardware sets in the store, sorted.

    This function is a generator as we do not want to expose the underlying list, which
    should only be modified in this module.

    The hardware sets are loaded lazily on the first call to this function. The reason
    for not automatically loading them when the module is imported is so that we can
    display an error dialog if it fails, for which we need a running QApplication.
    """
    if not _hw_sets:
        _load_all_hardware_sets()

    yield from _hw_sets


_hw_sets: list[HardwareSet] = []

pub.subscribe(_add_hardware_set, "hardware_set.add")
pub.subscribe(_remove_hardware_set, "hardware_set.remove")
