"""Panel and widgets related to monitoring the interferometer."""

from collections.abc import Sequence

from pubsub import pub
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from frog.config import SENSORS_TOPIC
from frog.gui.device_panel import DevicePanel
from frog.gui.led_icon import LEDIcon
from frog.sensor_reading import SensorReading


class SensorsPanel(DevicePanel):
    """Panel containing widgets to view sensor readings."""

    def __init__(self) -> None:
        """Create a new SensorsPanel."""
        super().__init__(SENSORS_TOPIC, "Sensor readings")

        self._val_lineedits: dict[str, QLineEdit] = {}

        self._poll_light = LEDIcon.create_green_icon()

        # As there may be many sensor readings, make the area scrollable
        self._reading_layout = QFormLayout()
        reading_widget = QWidget()
        reading_widget.setLayout(self._reading_layout)
        reading_area = QScrollArea()
        reading_area.setWidget(reading_widget)
        reading_area.setWidgetResizable(True)

        poll_layout = QFormLayout()
        poll_layout.addRow("POLL SERVER", self._poll_light)
        self._poll_light.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        layout = QVBoxLayout()
        layout.addWidget(reading_area)
        layout.addLayout(poll_layout)
        self.setLayout(layout)

        # Remove any existing sensor readings from panel
        pub.subscribe(self._remove_readings_widgets, f"device.opened.{SENSORS_TOPIC}")

        # Listen for readings sent by backend
        pub.subscribe(self._on_readings_received, f"device.{SENSORS_TOPIC}.data")

    def _remove_readings_widgets(self) -> None:
        """Remove all of the widgets for sensor readings."""
        self._val_lineedits.clear()
        while self._reading_layout.rowCount() > 0:
            self._reading_layout.removeRow(0)

    def _get_reading_lineedit(self, reading: SensorReading) -> QLineEdit:
        """Get or create the QLineEdit for a given sensor.

        Args:
            reading: The sensor reading to display

        Returns:
            QLineEdit: the QLineEdit widget corresponding to the reading
        """
        if reading.name not in self._val_lineedits:
            label = QLabel(reading.name)
            label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            val_lineedit = QLineEdit()
            val_lineedit.setReadOnly(True)
            val_lineedit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_lineedit.setSizePolicy(
                QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed
            )

            self._val_lineedits[reading.name] = val_lineedit
            self._reading_layout.addRow(reading.name, val_lineedit)

        return self._val_lineedits[reading.name]

    def _on_readings_received(self, readings: Sequence[SensorReading]):
        """Receive sensor readings from the backend and update the GUI.

        Args:
            readings: the latest sensor readings received
        """
        self._poll_light.flash()
        for reading in readings:
            lineedit = self._get_reading_lineedit(reading)
            lineedit.setText(reading.val_str())
