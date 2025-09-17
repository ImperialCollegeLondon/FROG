"""Provides a panel for choosing between hardware sets and (dis)connecting."""

from collections.abc import Mapping
from typing import Any, cast

from pubsub import pub
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from frog.device_info import DeviceInstanceRef
from frog.gui.hardware_set.device import ActiveDeviceManager
from frog.gui.hardware_set.device_view import DeviceControl
from frog.gui.hardware_set.hardware_set import (
    HardwareSet,
    get_hardware_sets,
)
from frog.gui.hardware_set.hardware_sets_combo_box import HardwareSetsComboBox
from frog.settings import settings


def _get_last_selected_hardware_set() -> HardwareSet | None:
    last_selected_path = cast(str | None, settings.value("hardware_set/selected"))
    if not last_selected_path:
        return None

    try:
        return next(
            hw_set
            for hw_set in get_hardware_sets()
            if str(hw_set.file_path) == last_selected_path
        )
    except StopIteration:
        # No hardware set matching this path
        return None


class ManageDevicesDialog(QDialog):
    """A dialog for manually opening, closing and configuring devices."""

    def __init__(self, device_manager: ActiveDeviceManager) -> None:
        """Create a new ManageDevicesDialog."""
        super().__init__()
        self.setWindowTitle("Manage devices")
        self.setModal(True)

        layout = QVBoxLayout()
        layout.addWidget(DeviceControl(device_manager))

        buttonbox = QDialogButtonBox()
        buttonbox.addButton(
            QPushButton("Close"), QDialogButtonBox.ButtonRole.RejectRole
        )
        buttonbox.rejected.connect(self.reject)
        layout.addWidget(buttonbox)

        self.setLayout(layout)


class HardwareSetsControl(QGroupBox):
    """A panel for choosing between hardware sets and (dis)connecting."""

    def __init__(
        self,
        device_manager: ActiveDeviceManager | None = None,
    ) -> None:
        """Create a new HardwareSetsControl."""
        super().__init__("Hardware set")

        if not device_manager:
            device_manager = ActiveDeviceManager()
        device_manager.device_started_open.connect(self._on_device_open_start)
        device_manager.device_opened.connect(self._on_device_open_end)
        device_manager.device_closed.connect(self._on_device_closed)
        self._device_manager = device_manager

        self._combo = HardwareSetsComboBox()
        """A combo box for the different hardware sets."""
        self._combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        if last_selected := _get_last_selected_hardware_set():
            self._combo.current_hardware_set = last_selected

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )
        self._connect_btn.pressed.connect(self._on_connect_btn_pressed)
        self._disconnect_btn = QPushButton("Disconnect all")
        self._disconnect_btn.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )
        self._disconnect_btn.pressed.connect(self._on_disconnect_btn_pressed)

        self._remove_hw_set_btn = QPushButton("Remove")
        self._remove_hw_set_btn.pressed.connect(self._remove_current_hardware_set)

        manage_devices_btn = QPushButton("Manage devices")
        manage_devices_btn.pressed.connect(self._show_manage_devices_dialog)
        self._manage_devices_dialog: ManageDevicesDialog

        row1 = QHBoxLayout()
        row1.addWidget(self._combo)
        row1.addWidget(self._connect_btn)
        row1.addWidget(self._disconnect_btn)
        row2 = QHBoxLayout()
        row2.addWidget(self._remove_hw_set_btn)
        row2.addWidget(manage_devices_btn)

        layout = QVBoxLayout()
        layout.addLayout(row1)
        layout.addLayout(row2)
        self.setLayout(layout)

        self._update_control_state()

        self._combo.currentIndexChanged.connect(self._update_control_state)

    def _remove_current_hardware_set(self) -> None:
        """Remove the currently selected hardware set."""
        pub.sendMessage("hardware_set.remove", hw_set=self._combo.current_hardware_set)

    def _show_manage_devices_dialog(self) -> None:
        """Show a dialog for managing devices manually.

        The dialog is created lazily.
        """
        if not hasattr(self, "_manage_devices_dialog"):
            self._manage_devices_dialog = ManageDevicesDialog(self._device_manager)

        self._manage_devices_dialog.show()

    def _update_control_state(self) -> None:
        """Enable or disable the connect and disconnect buttons as appropriate."""
        # Enable the "Connect" button if there are any devices left to connect for this
        # hardware set
        connected_devices = set(self._device_manager.get_connected_devices())
        all_connected = connected_devices.issuperset(
            self._combo.current_hardware_set_devices
        )
        any_devices_connecting = len(connected_devices) < len(
            self._device_manager.get_active_devices()
        )
        self._connect_btn.setEnabled(not any_devices_connecting and not all_connected)

        # Enable the "Disconnect all" button if there are *any* devices connected at all
        self._disconnect_btn.setEnabled(bool(connected_devices))

        # Enable the "Remove" button only if the hardware set is not a built in one
        hw_set = self._combo.current_hardware_set
        self._remove_hw_set_btn.setEnabled(hw_set is not None and not hw_set.built_in)

    def _on_connect_btn_pressed(self) -> None:
        """Connect to all devices in current hardware set.

        If a device has already been opened with the same type and parameters, then we
        skip it. If a device of the same type but with different parameters has been
        opened, then it will be closed as we open the new device.
        """
        # Something in the combo box will have been selected, so it won't be None
        path = self._combo.current_hardware_set.file_path  # type: ignore[union-attr]

        # Remember which hardware set was selected for next time we run the program
        settings.setValue(
            "hardware_set/selected",
            str(path),
        )

        # Open each of the devices in turn
        for device in self._combo.current_hardware_set_devices.difference(
            self._device_manager.get_active_devices()
        ):
            device.open()

    def _on_device_open_start(
        self, instance: DeviceInstanceRef, class_name: str, params: Mapping[str, Any]
    ) -> None:
        """Update GUI."""
        self._update_control_state()

    def _on_device_closed(self, instance: DeviceInstanceRef) -> None:
        """Update GUI."""
        self._update_control_state()

    def _on_disconnect_btn_pressed(self) -> None:
        """Disconnect from all devices in current hardware set."""
        self._device_manager.disconnect_all()

    def _on_device_open_end(self, instance: DeviceInstanceRef, class_name: str) -> None:
        """Add instance to _connected_devices and update GUI."""
        dev_props = self._device_manager.get_active_devices()[instance]

        # Remember last opened device
        settings.setValue(f"device/type/{instance!s}", class_name)
        if dev_props.args.params:
            settings.setValue(f"device/params/{class_name}", dev_props.args.params)

        self._update_control_state()
