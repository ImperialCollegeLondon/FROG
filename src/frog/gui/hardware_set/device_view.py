"""Provides a control for viewing and connecting to devices."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence, Set
from typing import Any, cast

from pubsub import pub
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from frog.device_info import DeviceBaseTypeInfo, DeviceInstanceRef, DeviceTypeInfo
from frog.gui.error_message import show_error_message
from frog.gui.hardware_set.device import (
    ConnectionStatus,
    OpenDeviceArgs,
    close_device,
    open_device,
)
from frog.gui.led_icon import LEDIcon
from frog.settings import settings


class ComboParameterWidget(QComboBox):
    """A widget showing the possible parameter values in a combo box."""

    def __init__(self, values: Sequence) -> None:
        """Create a new ComboParameterWidget.

        Args:
            values: The possible values for this parameter
        """
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Keep the "real" value along with its string representation, so that we can
        # pass it back to the backend on device open
        for value in values:
            self.addItem(str(value), value)

    @property
    def value(self) -> Any:
        """The currently selected parameter value."""
        return self.currentData()

    @value.setter
    def value(self, new_value: Any) -> Any:
        """Set the parameter value."""
        self.setCurrentText(str(new_value))


class TextParameterWidget(QLineEdit):
    """A widget allowing the user to enter parameter values into a text box."""

    def __init__(self, param_type: type) -> None:
        """Create a new TextParameterWidget.

        Args:
            param_type: The type that the parameter must be
        """
        super().__init__()
        self._param_type = param_type

    @property
    def value(self) -> Any:
        """The currently selected parameter value.

        Raises:
            Exception: If relevant type cannot be constructed from string
        """
        return self._param_type(self.text())

    @value.setter
    def value(self, new_value: Any) -> Any:
        """Set the parameter value."""
        self.setText(str(new_value))


ParameterWidget = ComboParameterWidget | TextParameterWidget
"""A type alias for a widget which supports getting and setting a parameter."""


class DeviceParametersWidget(QWidget):
    """A widget containing controls for setting a device's parameters."""

    def __init__(self, device_type: DeviceTypeInfo) -> None:
        """Create a new DeviceParametersWidget.

        Args:
            device_type: The device type whose parameters will be used
        """
        super().__init__()

        self.device_type = device_type
        """This value is not used within the class, but is stored for convenience."""

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        # Make a widget for each parameter
        self._param_widgets: dict[str, ParameterWidget] = {}
        for name, param in device_type.parameters.items():
            widget: ParameterWidget
            if isinstance(param.possible_values, Sequence):
                widget = ComboParameterWidget(param.possible_values)
            else:
                widget = TextParameterWidget(param.possible_values)

            widget.setToolTip(param.description)

            if param.default_value is not None:
                widget.value = param.default_value

            layout.addWidget(widget)
            self._param_widgets[name] = widget

        # If there are saved parameter values, load them now
        self.load_saved_parameter_values()

    def load_saved_parameter_values(self) -> None:
        """Set the combo boxes' parameter values according to their saved values."""
        params = cast(
            dict[str, Any] | None,
            settings.value(f"device/params/{self.device_type.class_name}"),
        )
        if not params:
            return

        for param, value in params.items():
            try:
                self._param_widgets[param].value = value
            except Exception as error:
                logging.warn(f"Error while setting param {param}: {error!s}")

    @property
    def current_parameter_values(self) -> dict[str, Any]:
        """Get all parameters and their current values."""
        return {param: widget.value for param, widget in self._param_widgets.items()}


class DeviceTypeControl(QGroupBox):
    """A set of widgets for choosing a device and its params and connecting to it."""

    def __init__(
        self,
        description: str,
        instance: DeviceInstanceRef,
        device_types: Sequence[DeviceTypeInfo],
        active_device_type: str | None = None,
        device_status: ConnectionStatus = ConnectionStatus.DISCONNECTED,
    ) -> None:
        """Create a new DeviceTypeControl.

        Args:
            description: A description of the device type
            instance: The device instance this panel is for
            device_types: The available devices for this base device type
            active_device_type: The class name for this device type, if opened
            device_status: The connection status for this device type
        """
        if not device_types:
            raise ValueError("At least one device type must be specified")
        if device_status == ConnectionStatus.DISCONNECTED:
            if active_device_type is not None:
                raise ValueError(
                    "active_device_type supplied even though status is disconnected"
                )
        elif not active_device_type:
            raise ValueError("Missing active_device_type")

        self._device_instance = instance

        super().__init__(description)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QHBoxLayout()
        self.setLayout(layout)

        self._device_combo = QComboBox()
        """Combo box allowing the user to choose the device."""
        self._device_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        # Add names for devices to combo box along with relevant user data
        self._device_widgets: list[DeviceParametersWidget] = []
        for t in device_types:
            widget = DeviceParametersWidget(t)
            widget.hide()  # will be shown when used

            self._device_combo.addItem(t.description, widget)

            # YUCK: We have to keep our own reference to widget, as self._device_combo
            # seemingly won't prevent it from being GC'd
            self._device_widgets.append(widget)

        # Select the last device that was successfully opened, if there is one
        previous_device = cast(str | None, settings.value(f"device/type/{instance!s}"))
        if previous_device:
            self._select_device(previous_device)

        layout.addWidget(self._device_combo)

        # Show the combo boxes for the device's parameters
        current_widget = self.current_device_type_widget
        current_widget.show()
        layout.addWidget(current_widget)

        self._status_control = ConnectionStatusControl()
        layout.addWidget(self._status_control)

        self._open_close_btn = QPushButton()
        self._open_close_btn.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._open_close_btn.clicked.connect(self._on_open_close_clicked)
        layout.addWidget(self._open_close_btn)

        if active_device_type:
            self._select_device(active_device_type)
        self._set_device_status(device_status)

        # Determine whether the button should be enabled or not
        self._update_open_btn_enabled_state()

        self._device_combo.currentIndexChanged.connect(self._on_device_selected)

        # pubsub subscriptions
        pub.subscribe(self._on_device_open_start, f"device.before_opening.{instance!s}")
        pub.subscribe(self._on_device_open_end, f"device.after_opening.{instance!s}")
        pub.subscribe(self._on_device_closed, f"device.closed.{instance!s}")

    def _set_device_status(self, status: ConnectionStatus) -> None:
        """Update the controls according to device connection status."""
        self._status_control.set_status(status)

        if status == ConnectionStatus.DISCONNECTED:
            self._set_combos_enabled(True)
            self._open_close_btn.setText("Open")
        else:
            self._set_combos_enabled(False)
            self._open_close_btn.setText("Close")

    def _update_open_btn_enabled_state(self) -> None:
        """Enable button depending on whether there are options for all params.

        The "open" button should be disabled if there are no possible values for any
        of the params.
        """
        all_params = self.current_device_type_widget.device_type.parameters.values()
        self._open_close_btn.setEnabled(all(p.possible_values for p in all_params))

    def _on_device_selected(self) -> None:
        """Swap out the parameter combo boxes for the current device."""
        layout = cast(QHBoxLayout, self.layout())

        # For some reason we also have to hide the widget else it appears over the
        # others
        layout.takeAt(1).widget().hide()

        # Add the widget for the newly selected parameter if needed
        widget = self.current_device_type_widget
        widget.show()
        layout.insertWidget(1, widget)

        # Enable/disable the "open" button
        self._update_open_btn_enabled_state()

    @property
    def current_device_type_widget(self) -> DeviceParametersWidget:
        """Get information about the currently selected device type."""
        return self._device_combo.currentData()

    def _set_combos_enabled(self, enabled: bool) -> None:
        """Set the enabled state of the combo boxes."""
        self._device_combo.setEnabled(enabled)
        self.current_device_type_widget.setEnabled(enabled)

    def _select_device(self, class_name: str) -> None:
        """Select the device from the combo box which matches class_name."""
        try:
            idx = next(
                i
                for i in range(self._device_combo.count())
                if self._device_combo.itemData(i).device_type.class_name == class_name
            )
        except StopIteration:
            logging.warn(f"Unknown class_name for opened device: {class_name}")
        else:
            self._device_combo.setCurrentIndex(idx)

            # Reload saved parameter values
            self._device_widgets[idx].load_saved_parameter_values()

    def _open_device(self) -> None:
        """Open the currently selected device."""
        widget = self.current_device_type_widget

        try:
            params = widget.current_parameter_values
        except ValueError:
            show_error_message(
                self,
                "Invalid value given for at least one parameter",
                "Invalid parameter value",
            )
        else:
            open_device(widget.device_type.class_name, self._device_instance, params)

    def _on_device_open_start(
        self, instance: DeviceInstanceRef, class_name: str, params: Mapping[str, Any]
    ) -> None:
        """Update the GUI when device opening starts."""
        self._select_device(class_name)
        self._set_device_status(ConnectionStatus.CONNECTING)

    def _on_device_open_end(self, instance: DeviceInstanceRef, class_name: str) -> None:
        """Update the GUI on device open."""
        self._select_device(class_name)
        self._set_device_status(ConnectionStatus.CONNECTED)

    def _on_device_closed(self, instance: DeviceInstanceRef) -> None:
        """Update the GUI on device close."""
        self._set_device_status(ConnectionStatus.DISCONNECTED)

    def _close_device(self) -> None:
        """Close the device."""
        close_device(self._device_instance)

    def _on_open_close_clicked(self) -> None:
        """Open/close the connection of the chosen device when the button is pushed."""
        if self._open_close_btn.text() == "Open":
            self._open_device()
        else:
            self._close_device()


class DeviceControl(QGroupBox):
    """Allows for viewing and connecting to devices."""

    def __init__(self, connected_devices: Set[OpenDeviceArgs]) -> None:
        """Create a new DeviceControl."""
        super().__init__("Device control")
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.setLayout(QVBoxLayout())
        self._connected_devices = connected_devices
        """The devices already connected when the control is created."""

        # Retrieve the list of device plugins
        pub.subscribe(self._on_device_list, "device.list.response")
        pub.sendMessage("device.list.request")

    def _get_connected_device(self, instance: DeviceInstanceRef) -> str | None:
        """Get the class name of the connected device matching instance, if any."""
        return next(
            (
                device.class_name
                for device in self._connected_devices
                if device.instance == instance
            ),
            None,
        )

    def _on_device_list(
        self, device_types: Mapping[DeviceBaseTypeInfo, Sequence[DeviceTypeInfo]]
    ) -> None:
        """Populate with DeviceTypeControls when a list of devices is received."""
        layout = cast(QVBoxLayout, self.layout())

        # Group together devices based on their base types (e.g. "stepper motor")
        for base_type, types in device_types.items():
            for instance, description in base_type.get_instances_and_descriptions():
                active_device_type = self._get_connected_device(instance)
                layout.addWidget(
                    DeviceTypeControl(
                        description,
                        instance,
                        types,
                        active_device_type,
                        # TODO: Handle connecting devices
                        ConnectionStatus.CONNECTED
                        if active_device_type
                        else ConnectionStatus.DISCONNECTED,
                    )
                )


class ConnectionStatusControl(QWidget):
    """A widget to show whether a device's connection status."""

    def __init__(
        self, initial_status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    ):
        """Create a new ConnectionStatusControl."""
        super().__init__()
        self._status: ConnectionStatus

        self._led = LEDIcon.create_green_icon()
        self._label = QLabel()

        layout = QHBoxLayout()
        layout.addWidget(self._led)
        layout.addWidget(self._label)
        self.setLayout(layout)

        self.set_status(initial_status)

    def set_status(self, status: ConnectionStatus) -> None:
        """Set the device status to display."""
        match status:
            case ConnectionStatus.DISCONNECTED:
                self._led.turn_off()
                self._label.setText("Disconnected")
            case ConnectionStatus.CONNECTING:
                self._led.turn_off()
                self._label.setText("Connecting...")
            case ConnectionStatus.CONNECTED:
                self._led.turn_on()
                self._label.setText("Connected")
