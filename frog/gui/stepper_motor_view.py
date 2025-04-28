"""Code for controlling the stepper motor which moves the mirror."""

from pubsub import pub
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QButtonGroup, QGridLayout, QLabel, QPushButton, QSpinBox

from frog.config import ANGLE_PRESETS, STEPPER_MOTOR_TOPIC
from frog.gui.device_panel import DevicePanel


class StepperMotorControl(DevicePanel):
    """A control showing buttons for moving the mirror to a target."""

    def __init__(self) -> None:
        """Create a new StepperMotorControl."""
        super().__init__(STEPPER_MOTOR_TOPIC, "Target control")

        layout = QGridLayout()

        # Bundle all the buttons for moving the mirror into one group
        self.button_group = QButtonGroup()
        self.button_group.buttonClicked.connect(self._preset_clicked)

        # Add all the buttons for preset positions
        BUTTONS_PER_ROW = 4
        for i, preset in enumerate(ANGLE_PRESETS):
            btn = self._add_checkable_button(preset.upper())
            self.button_group.addButton(btn)

            row, col = divmod(i, BUTTONS_PER_ROW)
            layout.addWidget(btn, row, col)

        # We also have a way for users to move the mirror to an angle of their choice
        self.angle = QSpinBox()
        self.angle.setMaximum(359)
        self.goto = self._add_checkable_button("GOTO")

        layout.addWidget(self.angle, 1, 2)
        layout.addWidget(self.goto, 1, 3)

        # Create widgets to show the current mirror position
        layout.addWidget(QLabel("Current position"), 0, 4)
        self.mirror_position_display = QLabel()
        self.mirror_position_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.mirror_position_display, 1, 4)

        self.setLayout(layout)

        pub.subscribe(
            self._indicate_moving,
            f"device.{STEPPER_MOTOR_TOPIC}.move.begin",
        )
        pub.subscribe(
            self._update_mirror_position_display,
            f"device.{STEPPER_MOTOR_TOPIC}.move.end",
        )

    def _add_checkable_button(self, name: str) -> QPushButton:
        """Add a selectable button to button_group."""
        btn = QPushButton(name)
        btn.setCheckable(True)

        self.button_group.addButton(btn)

        return btn

    def _preset_clicked(self, btn: QPushButton) -> None:
        """Move the stepper motor to preset position."""
        target = float(self.angle.value()) if btn is self.goto else btn.text().lower()
        pub.sendMessage(f"device.{STEPPER_MOTOR_TOPIC}.move.begin", target=target)

    def _indicate_moving(self, target) -> None:
        """Update the display the indicate that the mirror is moving."""
        self.mirror_position_display.setText("Moving...")

    def _update_mirror_position_display(self, moved_to: float) -> None:
        """Display the angle the mirror has moved to.

        If angle corresponds to a preset, show the associated name as well as the value.
        """
        text = f"{round(moved_to)}°"
        if preset := next((k for k, v in ANGLE_PRESETS.items() if v == moved_to), None):
            text += f" ({preset})"
        self.mirror_position_display.setText(text)
