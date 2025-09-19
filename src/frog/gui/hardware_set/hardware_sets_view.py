"""Provides a panel for choosing between hardware sets and (dis)connecting."""

from collections.abc import Mapping
from typing import Any, cast

from pubsub import pub
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
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


class HardwareSetNameDialog(QDialog):
    """A dialog for choosing a name for a new hardware set."""

    def __init__(self, parent: QWidget) -> None:
        """Create a new HardwareSetNameDialog."""
        super().__init__(parent)
        self.setWindowTitle("Device configuration name")

        layout = QGridLayout()
        layout.addWidget(QLabel("Name for device configuration:"), 0, 0)

        self._name_widget = QLineEdit()
        self._name_widget.setMinimumSize(200, self._name_widget.minimumHeight())
        layout.addWidget(self._name_widget, 0, 1)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box, 1, 0, 1, 2)

        self.setLayout(layout)

    def show_and_get_name(self) -> str | None:
        """Show the dialog and try to get the name chosen.

        If the user closes the dialog, None is returned.
        """
        while True:
            accepted = self.exec()
            if not accepted:
                # User cancelled
                return None

            name = self._name_widget.text().strip()
            if name:
                # Valid name chosen
                return name

            msgbox = QMessageBox(
                QMessageBox.Icon.Critical,
                "No name provided",
                "You must provide a name for the device configuration",
            )
            msgbox.exec()


class ManageDevicesDialog(QDialog):
    """A dialog for manually opening, closing and configuring devices."""

    def __init__(self, device_manager: ActiveDeviceManager) -> None:
        """Create a new ManageDevicesDialog."""
        super().__init__()
        self.setWindowTitle("Manage devices")
        self.setModal(True)

        device_manager.device_opened.connect(self._update_save_button_state)
        device_manager.device_closed.connect(self._update_save_button_state)
        self._device_manager = device_manager

        layout = QVBoxLayout()
        layout.addWidget(DeviceControl(device_manager))

        self._save_btn = QPushButton("Save device configuration")
        self._save_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        )
        self._save_btn.clicked.connect(self._save_hardware_set)

        buttonbox = QDialogButtonBox()
        buttonbox.addButton(self._save_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttonbox.addButton(
            QPushButton("Close"), QDialogButtonBox.ButtonRole.RejectRole
        )
        buttonbox.rejected.connect(self.reject)
        layout.addWidget(buttonbox)

        self.setLayout(layout)

        self._update_save_button_state()

    def _save_hardware_set(self) -> None:
        """Save the device manager's current state as a new hardware set."""
        if name := HardwareSetNameDialog(self).show_and_get_name():
            # Create a hardware set from the currently connected devices
            hw_set = HardwareSet.from_devices(
                name, self._device_manager.connected_devices
            )

            # Save it and add to the list of hardware sets displayed in the GUI
            pub.sendMessage("hardware_set.add", hw_set=hw_set)

            # Close this dialog
            self.accept()

    def _update_save_button_state(self) -> None:
        """Enable/disable the save button.

        The button will be enabled if any devices are connected (connecting devices
        don't count) and disabled otherwise.
        """
        any_devices_connected = bool(
            next(self._device_manager.connected_devices, None)  # type: ignore
        )
        self._save_btn.setEnabled(any_devices_connected)


class HardwareSetsControl(QGroupBox):
    """A panel for choosing between hardware sets and (dis)connecting."""

    def __init__(
        self,
        device_manager: ActiveDeviceManager | None = None,
    ) -> None:
        """Create a new HardwareSetsControl."""
        super().__init__("Devices")

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
        connected_devices = set(self._device_manager.connected_devices)
        all_connected = connected_devices.issuperset(
            self._combo.current_hardware_set_devices
        )
        any_devices_connecting = len(connected_devices) < len(
            self._device_manager.devices
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
            self._device_manager.devices
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
        dev_props = self._device_manager.devices[instance]

        # Remember last opened device
        settings.setValue(f"device/type/{instance!s}", class_name)
        if dev_props.args.params:
            settings.setValue(f"device/params/{class_name}", dev_props.args.params)

        self._update_control_state()
