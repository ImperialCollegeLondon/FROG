"""Tests for StepperMotorControl."""

from typing import cast
from unittest.mock import MagicMock, Mock, patch

import pytest
from PySide6.QtWidgets import QButtonGroup, QLabel, QPushButton
from pytestqt.qtbot import QtBot

from frog.config import ANGLE_PRESETS, STEPPER_MOTOR_TOPIC
from frog.gui.stepper_motor_view import StepperMotorControl


@patch("frog.gui.stepper_motor_view.QButtonGroup")
def test_init(button_group_mock: Mock, qtbot: QtBot) -> None:
    """Test StepperMotorControl's constructor."""
    button_group = QButtonGroup()
    button_group_mock.return_value = button_group
    with patch.object(button_group, "buttonClicked") as clicked_mock:
        control = StepperMotorControl()

        # Check that button_group's signal is connected
        clicked_mock.connect.assert_called_once_with(control._preset_clicked)

        # Check that there is a button for each preset angle
        btn_labels = {btn.text().lower() for btn in button_group.buttons()}
        assert set(ANGLE_PRESETS.keys()).issubset(btn_labels)

        # Check that there's also a goto button
        assert "goto" in btn_labels

    # Check that mirror position widgets have been created
    current_position_label = control.layout().itemAt(8).widget()  # type: ignore[union-attr]
    assert isinstance(current_position_label, QLabel)
    assert current_position_label.text() == "Current position"
    assert control.mirror_position_display.text() == ""


@pytest.mark.parametrize("preset", ANGLE_PRESETS.keys())
def test_preset_clicked(preset: str, sendmsg_mock: MagicMock, qtbot: QtBot) -> None:
    """Test the _preset_clicked() method."""
    control = StepperMotorControl()

    # Get the button for this preset
    btn = next(
        btn for btn in control.button_group.buttons() if btn.text().lower() == preset
    )
    btn = cast(QPushButton, btn)

    # The motor should be stopped and then moved to this preset
    control._preset_clicked(btn)
    sendmsg_mock.assert_any_call(f"device.{STEPPER_MOTOR_TOPIC}.stop")
    sendmsg_mock.assert_any_call(
        f"device.{STEPPER_MOTOR_TOPIC}.move.begin", target=preset
    )


def test_goto_clicked(sendmsg_mock: MagicMock, qtbot: QtBot) -> None:
    """Test that the GOTO button works."""
    control = StepperMotorControl()

    with patch.object(control.angle, "value") as angle_mock:
        angle_mock.return_value = 123

        # The motor should be stopped then moved to 123°
        control._preset_clicked(control.goto)
        sendmsg_mock.assert_any_call(f"device.{STEPPER_MOTOR_TOPIC}.stop")
        sendmsg_mock.assert_any_call(
            f"device.{STEPPER_MOTOR_TOPIC}.move.begin", target=123.0
        )


def test_indicate_moving(qtbot: QtBot) -> None:
    """Test the mirror position display updates correctly."""
    control = StepperMotorControl()

    control._indicate_moving(target="target")
    assert control.mirror_position_display.text() == "Moving..."


def test_update_mirror_position_display(qtbot: QtBot) -> None:
    """Test the mirror position display updates correctly."""
    control = StepperMotorControl()

    control._update_mirror_position_display(moved_to=ANGLE_PRESETS["zenith"])
    assert control.mirror_position_display.text() == "180\u00b0 (zenith)"

    control._update_mirror_position_display(moved_to=12.34)
    assert control.mirror_position_display.text() == "12\u00b0"
