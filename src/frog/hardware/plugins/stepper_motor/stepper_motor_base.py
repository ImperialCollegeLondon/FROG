"""Provides the base class for stepper motor implementations."""

from abc import abstractmethod

from frozendict import frozendict

from frog.config import STEPPER_MOTOR_TOPIC
from frog.hardware.device import Device


class StepperMotorBase(Device, name=STEPPER_MOTOR_TOPIC, description="Stepper motor"):
    """A base class for stepper motor implementations."""

    ANGLE_PRESET_DEFAULTS = frozendict(zenith=180.0, nadir=0.0, home=0.0, park=90.0)
    """Values for preset angles that the mirror can rotate to.

    This does not include angles for hot_bb and cold_bb as these can be configured by
    users.
    """

    def __init__(self, hot_bb_angle: float, cold_bb_angle: float) -> None:
        """Create a new StepperMotorBase.

        Args:
            hot_bb_angle: Angle of hot black body relative to nadir (degrees)
            cold_bb_angle: Angle of cold black body relative to nadir (degrees)

        Subscribe to stepper motor pubsub messages.
        """
        super().__init__()

        if not (0.0 <= hot_bb_angle < 360.0):
            raise ValueError("Hot BB angle must be >= 0° and < 360°")
        if not (0.0 <= cold_bb_angle < 360.0):
            raise ValueError("Cold BB angle must be >= 0° and < 360°")

        self.angle_presets = frozendict(
            **self.ANGLE_PRESET_DEFAULTS, hot_bb=hot_bb_angle, cold_bb=cold_bb_angle
        )

        self.subscribe(self.move_to, "move.begin")
        self.subscribe(self.stop_moving, "stop")

    def signal_is_opened(self) -> None:
        """Signal that the device is now open."""
        super().signal_is_opened()
        self.send_message("angle_presets", angle_presets=self.angle_presets)

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
            try:
                target = self.angle_presets[target]
            except KeyError:
                raise ValueError(f'"{target}" is not a valid angle preset')
        elif target < 0.0 or target >= 360.0:
            raise ValueError("Angle must be between 0° and 360°")

        self.step = round(self.steps_per_rotation * target / 360.0)  # type: ignore[operator]

    def send_move_end_message(self) -> None:
        """Send a message containing the angle moved to, once move ends."""
        self.send_message("move.end", moved_to=self.angle)
