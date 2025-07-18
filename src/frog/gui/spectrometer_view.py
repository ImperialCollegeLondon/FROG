"""Panel and widgets related to the control of spectrometers."""

from collections.abc import Mapping
from functools import partial

from frozendict import frozendict
from pubsub import pub
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from frog.config import SPECTROMETER_TOPIC
from frog.gui.device_panel import DevicePanel
from frog.spectrometer_status import SpectrometerStatus


class SpectrometerControl(DevicePanel):
    """Class to monitor and control spectrometers."""

    _COMMANDS = frozendict(
        {
            "connect": "Connect",
            "start_measuring": "Start",
            "stop_measuring": "Stop",
        }
    )
    """The default commands shown (key=command, value=label)."""

    _ENABLED_BUTTONS = frozendict(
        {
            SpectrometerStatus.IDLE: {"connect"},
            SpectrometerStatus.CONNECTED: {"start_measuring"},
            SpectrometerStatus.MEASURING: {"stop_measuring"},
        }
    )
    """Which buttons to enable for different states."""

    def __init__(self, commands: Mapping[str, str] = _COMMANDS) -> None:
        """Create the widgets to monitor and control the spectrometer."""
        super().__init__(SPECTROMETER_TOPIC, "Spectrometer")

        self._buttons: dict[str, QPushButton] = {}
        """Buttons for the different spectrometer commands."""
        self._status_label = QLabel("Status:")
        """A label showing the current status of the device."""

        layout = QVBoxLayout()
        layout.addLayout(self._create_buttons(commands))
        layout.addWidget(self._status_label)
        self.setLayout(layout)

        pub.subscribe(self._on_status_changed, f"device.{SPECTROMETER_TOPIC}.status")

    def _create_buttons(self, commands: Mapping[str, str]) -> QHBoxLayout:
        """Creates the buttons.

        Returns:
            The layout with the buttons
        """
        btn_layout = QHBoxLayout()

        for command, label in commands.items():
            button = QPushButton(label)
            button.setEnabled(False)
            button.clicked.connect(
                partial(self.on_command_button_clicked, command=command)
            )
            btn_layout.addWidget(button)

            self._buttons[command] = button

        return btn_layout

    def _on_status_changed(self, status: SpectrometerStatus) -> None:
        """Update the GUI based on the status."""
        self._status_label.setText(f"Status: <b>{status.name}</b>")

        # Enable/disable buttons depending on the spectrometer's status
        to_enable = self._ENABLED_BUTTONS.get(status, set())
        for command, btn in self._buttons.items():
            btn.setEnabled(command in to_enable)

    def on_command_button_clicked(self, command: str) -> None:
        """Execute the given command by sending a message to the appropriate topic.

        Args:
            command: Command to be executed
        """
        pub.sendMessage(f"device.{SPECTROMETER_TOPIC}.{command}")
