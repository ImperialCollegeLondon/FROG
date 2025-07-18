"""Provides a widget for interacting with temperature controllers."""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from pubsub import pub
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
)

from frog.config import (
    TEMPERATURE_CONTROLLER_POLL_INTERVAL,
    TEMPERATURE_CONTROLLER_TOPIC,
    TEMPERATURE_MONITOR_TOPIC,
)
from frog.device_info import DeviceInstanceRef
from frog.gui.device_panel import DevicePanel
from frog.gui.led_icon import LEDIcon


class TemperatureControllerControl(DevicePanel):
    """A widget to interact with temperature controllers."""

    def __init__(self, name: str, temperature_idx: int, allow_update: bool) -> None:
        """Create a new TemperatureControllerControl.

        Args:
            name: Name of the blackbody the temperature controller is controlling
            temperature_idx: Index of the blackbody on the temperature monitor
            allow_update: Whether to allow modifying the temperature
        """
        super().__init__(
            f"{TEMPERATURE_CONTROLLER_TOPIC}.{name}_bb",
            f"Temperature controller ({name} BB)",
        )
        self._name = name
        self._poll_interval = 1000 * TEMPERATURE_CONTROLLER_POLL_INTERVAL
        self._temperature_idx = temperature_idx

        layout = self._create_controls(allow_update)
        self.setLayout(layout)

        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        pub.subscribe(
            self._begin_polling,
            f"device.opened.{TEMPERATURE_CONTROLLER_TOPIC}.{name}_bb",
        )
        pub.subscribe(
            self._update_controls,
            f"device.{TEMPERATURE_CONTROLLER_TOPIC}.{name}_bb.response",
        )
        pub.subscribe(
            self._update_pt100, f"device.{TEMPERATURE_MONITOR_TOPIC}.data.response"
        )

    def _create_controls(self, allow_update: bool) -> QGridLayout:
        """Creates the overall layout for the panel.

        Returns:
            QGridLayout: The layout containing the figure.
        """
        layout = QGridLayout()

        align = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        control_label = QLabel("CONTROL")
        control_label.setAlignment(align)
        layout.addWidget(control_label, 0, 0)

        power_label = QLabel("POWER")
        power_label.setAlignment(align)
        layout.addWidget(power_label, 1, 0)

        set_label = QLabel("SET")
        set_label.setAlignment(align)
        layout.addWidget(set_label, 2, 0)

        pt100_label = QLabel("Pt 100")
        pt100_label.setAlignment(align)
        layout.addWidget(pt100_label, 0, 2)

        poll_label = QLabel("POLL")
        poll_label.setAlignment(align)
        layout.addWidget(poll_label, 0, 4)

        alarm_label = QLabel("ALARM")
        alarm_label.setAlignment(align)
        layout.addWidget(alarm_label, 2, 4)

        self._control_val = QLineEdit()
        self._control_val.setReadOnly(True)
        self._control_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._control_val, 0, 1)

        self._pt100_val = QLineEdit()
        self._pt100_val.setReadOnly(True)
        self._pt100_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._pt100_val, 0, 3)

        self._power_bar = QProgressBar()
        self._power_bar.setRange(0, 100)
        self._power_bar.setTextVisible(False)
        self._power_bar.setOrientation(Qt.Orientation.Horizontal)
        layout.addWidget(self._power_bar, 1, 1, 1, 3)

        self._power_label = QLineEdit()
        self._power_label.setReadOnly(True)
        layout.addWidget(self._power_label, 1, 4)

        self._poll_light = LEDIcon.create_green_icon()
        self._poll_light.timer.timeout.connect(self._poll_device)
        self._alarm_light = LEDIcon.create_red_icon()
        layout.addWidget(self._poll_light, 0, 5)
        layout.addWidget(self._alarm_light, 2, 5)

        self._set_sbox = QSpinBox()
        layout.addWidget(self._set_sbox, 2, 1)

        self._update_pbtn = QPushButton("UPDATE")
        self._update_pbtn.setCheckable(True)
        self._update_pbtn.setEnabled(allow_update)
        self._update_pbtn.clicked.connect(self._on_update_clicked)
        layout.addWidget(self._update_pbtn, 2, 3)

        return layout

    def _on_update_clicked(self) -> None:
        isDown = self._update_pbtn.isChecked()
        if isDown:
            self._set_sbox.setEnabled(True)
            self._end_polling()
        else:
            self._set_new_set_point()
            self._set_sbox.setEnabled(False)
            self._begin_polling()

    def _on_device_closed(self, instance: DeviceInstanceRef) -> None:
        super()._on_device_closed(instance)
        self._end_polling()

    def _begin_polling(self) -> None:
        """Initiate polling the device."""
        # DevicePanel.set_controls_enabled() will enable these, but we want them to
        # begin disabled
        self._set_sbox.setEnabled(False)
        self._poll_device()
        self._poll_light.timer.start(self._poll_interval)

    def _end_polling(self) -> None:
        """Terminate polling the device."""
        self._poll_light.timer.stop()

    def _poll_device(self) -> None:
        """Polls the device to obtain the latest info."""
        self._poll_light.flash()
        pub.sendMessage(
            f"device.{TEMPERATURE_CONTROLLER_TOPIC}.{self._name}_bb.request"
        )

    def _update_controls(self, properties: dict):
        """Update panel with latest info from temperature controller.

        Args:
            properties: dictionary containing the retrieved properties
        """
        self._control_val.setText(f"{properties['temperature']: .2f}")
        self._power_bar.setValue(properties["power"])
        self._power_label.setText(f"{round(properties['power'])}")
        self._set_sbox.setValue(int(properties["set_point"]))
        if properties["alarm_status"] != 0:
            self._alarm_light.turn_on()
        elif self._alarm_light._is_on:
            self._alarm_light.turn_off()

    def _update_pt100(self, temperatures: Sequence, time: datetime):
        """Show the latest blackbody temperature.

        Args:
            temperatures: list of temperatures retrieved from device
            time: the timestamp at which the properties were sent
        """
        self._pt100_val.setText(f"{temperatures[self._temperature_idx]: .2f}")

    def _set_new_set_point(self) -> None:
        """Send new target temperature to temperature controller."""
        pub.sendMessage(
            f"device.{TEMPERATURE_CONTROLLER_TOPIC}.{self._name}_bb.change_set_point",
            temperature=Decimal(self._set_sbox.value()),
        )
