"""Provides a class for monitoring events such as device opening/closing."""

from collections.abc import Callable, Sequence
from typing import Any

from pubsub import pub

from frog.device_info import DeviceInstanceRef


class EventCounter:
    """A class for monitoring events such as device opening/closing.

    Callbacks are run when the desired count is reached and when the count drops below
    the target.
    """

    def __init__(
        self,
        on_target_reached: Callable[[], Any],
        on_below_target: Callable[[], Any],
        target_count: int | None = None,
        device_names: Sequence[str] = (),
    ) -> None:
        """Create a new EventCounter.

        Args:
            on_target_reached: Callback for when target_count is reached
            on_below_target: Callback for when count drops below target_count
            target_count: The target count on which on_target_reached will be run
            device_names: The names of serial device topics to subscribe to
        """
        if target_count is None:
            if not device_names:
                raise ValueError("Must supply either target_count or device_names")
            target_count = len(device_names)

        self._count = 0
        self._target_count = target_count
        self._on_target_reached = on_target_reached
        self._on_below_target = on_below_target

        # Subscribe to devices' open/close messages
        for name in device_names:
            pub.subscribe(self.increment, f"device.opened.{name}")
            pub.subscribe(self._on_device_closed, f"device.closed.{name}")

    def increment(self) -> None:
        """Increase the counter by one and run callback if target reached."""
        self._count += 1
        if self._count == self._target_count:
            self._on_target_reached()

    def decrement(self) -> None:
        """Decrease the counter by one and run callback if count drops below target."""
        self._count -= 1
        if self._count == self._target_count - 1:
            self._on_below_target()

    def _on_device_closed(self, instance: DeviceInstanceRef) -> None:
        """Decrease the counter on device close."""
        self.decrement()
