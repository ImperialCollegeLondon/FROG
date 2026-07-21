"""Code for controlling the stepper motor which moves the mirror."""

from collections.abc import Mapping

from pubsub import pub
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDoubleSpinBox,
    QGridLayout,
    QLabel,
    QPushButton,
)

from frog.config import ANGLE_PRESET_NAMES, STEPPER_MOTOR_TOPIC
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
        for i, preset in enumerate(ANGLE_PRESET_NAMES):
            btn = self._add_checkable_button(preset.upper())
            self.button_group.addButton(btn)

            row, col = divmod(i, BUTTONS_PER_ROW)
            layout.addWidget(btn, row, col)

        # We also have a way for users to move the mirror to an angle of their choice
        self.angle = QDoubleSpinBox()
        self.angle.setDecimals(1)
        self.angle.setSingleStep(0.1)
        self.angle.setMaximum(359.9)
        self.goto = self._add_checkable_button("GOTO")

        layout.addWidget(self.angle, 1, 2)
        layout.addWidget(self.goto, 1, 3)

        # Create widgets to show the current mirror position
        layout.addWidget(QLabel("Current position"), 0, 4)
        self.mirror_position_display = QLabel()
        self.mirror_position_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.mirror_position_display, 1, 4)

        self.setLayout(layout)

        self.angle_presets: Mapping[str, float]
        pub.subscribe(
            self._update_preset_angles, f"device.{STEPPER_MOTOR_TOPIC}.angle_presets"
        )
        pub.subscribe(
            self._indicate_moving,
            f"device.{STEPPER_MOTOR_TOPIC}.move.begin",
        )
        pub.subscribe(
            self._on_move_end,
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

    def _update_preset_angles(self, angle_presets: Mapping[str, float]) -> None:
        """Update the values of the preset angles."""
        self.angle_presets = angle_presets

    def _indicate_moving(self, target) -> None:
        """Update the display the indicate that the mirror is moving."""
        self.mirror_position_display.setText("Moving...")

    def _on_move_end(self, moved_to: float) -> None:
        """Update the control to show the angle that the mirror has moved to.

        This is displayed in a text label, which will include the preset name, if the
        angle (approximately) corresponds to a preset. The relevant preset button will
        also be checked/unchecked as appropriate.
        """
        text = f"{moved_to:.1f}°"
        if preset := next(
            (k for k, v in self.angle_presets.items() if abs(v - moved_to) <= 0.05),
            None,
        ):
            # If this angle corresponds to a preset, include name in label
            text += f" ({preset})"

            # Also check the corresponding preset button
            preset_upper = preset.upper()
            preset_btn = next(
                btn for btn in self.button_group.buttons() if btn.text() == preset_upper
            )
            preset_btn.setChecked(True)
        elif btn := self.button_group.checkedButton():
            # This angle isn't a preset. If there is a button already checked, uncheck
            # it.
            #
            # Alas, you can't uncheck a button if it's in an exclusive group, as here,
            # so we make the group non-exclusive, uncheck the button, then make the
            # group exclusive again.
            #
            # See: https://forum.qt.io/topic/6419/how-to-uncheck-button-in-qbuttongroup
            self.button_group.setExclusive(False)
            btn.setChecked(False)
            self.button_group.setExclusive(True)

        self.mirror_position_display.setText(text)
