"""Provides a combo box for choosing between hardware sets."""

from pubsub import pub
from PySide6.QtWidgets import QComboBox

from frog.gui.hardware_set.device import OpenDeviceArgs
from frog.gui.hardware_set.hardware_set import (
    HardwareSet,
    get_hardware_sets,
)


class HardwareSetsComboBox(QComboBox):
    """A combo box for choosing between hardware sets."""

    def __init__(self) -> None:
        """Create a new HardwareSetsComboBox."""
        super().__init__()
        self._load_hardware_set_list()

        pub.subscribe(self._on_hardware_set_added, "hardware_set.added")
        pub.subscribe(self._load_hardware_set_list, "hardware_set.removed")

    def _load_hardware_set_list(self) -> None:
        """Populate the combo box with hardware sets."""
        self.clear()
        for hw_set in get_hardware_sets():
            self._add_hardware_set(hw_set)

    def _add_hardware_set(self, hw_set: HardwareSet) -> None:
        """Add a new hardware set to the combo box."""
        labels = {self.itemText(i) for i in range(self.count())}

        name_root = hw_set.name
        if hw_set.built_in:
            name_root += " (built in)"

        if name_root not in labels:
            self.addItem(name_root, hw_set)
            return

        # If there is already a hardware set by that name, append a number
        i = 2
        while True:
            name = f"{name_root} ({i})"
            if name not in labels:
                self.addItem(name, hw_set)
                return
            i += 1

    def _on_hardware_set_added(self, hw_set: HardwareSet) -> None:
        """Clear the combo box and refill it, then select hw_set.

        The reason for clearing the combo box and refilling it is so that we can keep
        the entries sorted.
        """
        self._load_hardware_set_list()

        # Select the just-added hardware set
        self.current_hardware_set = hw_set

    @property
    def current_hardware_set(self) -> HardwareSet | None:
        """Return the currently selected hardware set.

        Returns None if no item is selected.
        """
        return self.currentData()

    @current_hardware_set.setter
    def current_hardware_set(self, hw_set: HardwareSet) -> None:
        try:
            idx = next(i for i in range(self.count()) if self.itemData(i) is hw_set)
        except StopIteration:
            raise ValueError(f'Hardware set "{hw_set.name}" not found')
        else:
            self.setCurrentIndex(idx)

    @property
    def current_hardware_set_devices(self) -> frozenset[OpenDeviceArgs]:
        """Return the currently selected hardware set's devices.

        If the combo box is empty and, therefore, no hardware set is selected, an empty
        set is returned.
        """
        hw_set = self.current_hardware_set
        return hw_set.devices if hw_set else frozenset()
