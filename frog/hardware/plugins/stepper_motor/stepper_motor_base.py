"""Provides the base class for stepper motor implementations."""

from abc import abstractmethod

from frog.config import ANGLE_PRESETS, STEPPER_MOTOR_TOPIC
from frog.hardware.device import Device


class StepperMotorBase(Device, name=STEPPER_MOTOR_TOPIC, description="Stepper motor"):
    """A base class for stepper motor implementations."""

    def __init__(self) -> None:
        """Create a new StepperMotorBase.

        Subscribe to stepper motor pubsub messages.
        """
        super().__init__()

        self.subscribe(self.move_to, "move.begin")
        self.subscribe(self.stop_moving, "stop")

    @staticmethod
    def preset_angle(name: str) -> float:
        """Get the angle for one of the preset positions.

        Args:
            name: Name of preset angle

        Returns:
            The angle in degrees
        """
        try:
            return ANGLE_PRESETS[name]
        except KeyError as e:
            raise ValueError(f"{name} is not a valid preset") from e

    @property
    @abstractmethod
    def steps_per_rotation(self) -> int:
        """The number of steps that correspond to a full rotation."""

    @property
    @abstractmethod
    def step(self) -> int:
        """The current state of the device's step counter."""

    @step.setter
    @abstractmethod
    def step(self, step: int) -> None:
        """Move the stepper motor to the specified absolute position.

        Args:
            step: Which step position to move to
        """

    @abstractmethod
    def stop_moving(self) -> None:
        """Immediately stop moving the motor."""

    @property
    @abstractmethod
    def is_moving(self) -> bool:
        """Whether the motor is currently moving."""

    @property
    def angle(self) -> float:
        """The current angle of the motor in degrees.

        Returns:
            The current angle
        """
        return self.step * 360.0 / self.steps_per_rotation

    def move_to(self, target: float | str) -> None:
        """Move the motor to a specified rotation and send message when complete.

        Args:
            target: The target angle (in degrees) or the name of a preset
        """
        if isinstance(target, str):
            target = self.preset_angle(target)

        if target < 0.0 or target >= 360.0:
            raise ValueError("Angle must be between 0° and 360°")

        self.step = round(self.steps_per_rotation * target / 360.0)

    def send_move_end_message(self) -> None:
        """Send a message containing the angle moved to, once move ends."""
        self.send_message("move.end", moved_to=self.angle)
