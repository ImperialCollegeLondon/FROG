"""Provides a widget to show the current temperatures."""

from collections.abc import Sequence
from datetime import datetime

from pubsub import pub
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
)

from frog.config import (
    NUM_TEMPERATURE_MONITOR_CHANNELS,
    TEMPERATURE_MONITOR_POLL_INTERVAL,
    TEMPERATURE_MONITOR_TOPIC,
)
from frog.gui.device_panel import DevicePanel
from frog.gui.led_icon import LEDIcon


class TemperatureMonitorControl(DevicePanel):
    """Widgets to view the current temperatures."""

    def __init__(self, num_channels: int = NUM_TEMPERATURE_MONITOR_CHANNELS) -> None:
        """Creates the widgets to monitor the current temperatures.

        Args:
            num_channels: Number of Pt 100 channels being monitored
        """
        super().__init__(TEMPERATURE_MONITOR_TOPIC, "Temperature monitor")

        self._num_channels = num_channels
        self._poll_interval = 1000 * TEMPERATURE_MONITOR_POLL_INTERVAL

        layout = self._create_controls()
        self.setLayout(layout)

        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        pub.subscribe(
            self._update_pt100s, f"device.{TEMPERATURE_MONITOR_TOPIC}.data.response"
        )

        self._begin_polling()

    def _create_controls(self) -> QGridLayout:
        """Creates the overall layout for the panel.

        Returns:
            QGridLayout: The layout containing the figure.
        """
        layout = QGridLayout()

        layout.addWidget(QLabel("Pt 100"), 1, 0)
        self._channels = []
        for i in range(self._num_channels):
            channel_label = QLabel(f"CH_{i + 1}")
            channel_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(channel_label, 0, i + 1)

            channel_tbox = QLineEdit()
            channel_tbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
            channel_tbox.setReadOnly(True)
            self._channels.append(channel_tbox)
            layout.addWidget(channel_tbox, 1, i + 1)

        poll_label = QLabel("POLL")
        poll_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(poll_label, 0, 9, 2, 1)

        self._poll_light = LEDIcon.create_green_icon()
        self._poll_light.timer.setInterval(self._poll_interval)
        self._poll_light.timer.timeout.connect(self._poll_device)
        layout.addWidget(self._poll_light, 0, 10, 2, 1)

        return layout

    def _begin_polling(self) -> None:
        """Initiate polling the temperature monitor."""
        self._poll_device()
        self._poll_light.timer.start()

    def _poll_device(self) -> None:
        """Polls the device to obtain the latest values."""
        self._poll_light.flash()
        pub.sendMessage(f"device.{TEMPERATURE_MONITOR_TOPIC}.data.request")

    def _update_pt100s(self, temperatures: Sequence, time: datetime) -> None:
        """Display the latest Pt 100 temperatures.

        Args:
            temperatures: current temperatures
            time: when the temperatures were retrieved
        """
        for channel, temperature in zip(self._channels, temperatures):
            channel.setText(f"{temperature: .2f}")
