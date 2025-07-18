"""Class for LED Icons."""

from __future__ import annotations

from importlib import resources

from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel

_img_files = resources.files("frog.gui.images")
_green_on_img_data = _img_files.joinpath("green_on.png").read_bytes()
_green_off_img_data = _img_files.joinpath("green_off.png").read_bytes()
_red_on_img_data = _img_files.joinpath("red_on.png").read_bytes()
_red_off_img_data = _img_files.joinpath("red_off.png").read_bytes()

_green_on_img = QImage.fromData(_green_on_img_data)
_green_off_img = QImage.fromData(_green_off_img_data)
_red_on_img = QImage.fromData(_red_on_img_data)
_red_off_img = QImage.fromData(_red_off_img_data)


class LEDIcon(QLabel):
    """QLabel object to represent an LED with on/off status."""

    def __init__(self, on_img: QImage, off_img: QImage, is_on: bool = False) -> None:
        """Creates the LED icon, sets its status and stores corresponding image data.

        Args:
            on_img (QImage): QImage for LED on state.
            off_img (QImage): QImage for LED off state.
            is_on (bool): On/off status of LED.
        """
        super().__init__()
        self._on_img = on_img
        self._off_img = off_img
        if is_on:
            self.turn_on()
        else:
            self.turn_off()
        self.timer = QTimer()
        self.timer.timeout.connect(self.turn_off)

    @classmethod
    def create_green_icon(cls) -> LEDIcon:
        """Creates a green LED icon."""
        return cls(on_img=_green_on_img, off_img=_green_off_img)

    @classmethod
    def create_red_icon(cls) -> LEDIcon:
        """Creates a red LED icon."""
        return cls(on_img=_red_on_img, off_img=_red_off_img)

    def turn_on(self) -> None:
        """Turns the LED on."""
        self._is_on = True
        self.setPixmap(QPixmap(self._on_img))

    def turn_off(self) -> None:
        """Turns the LED off."""
        self._is_on = False
        self.setPixmap(QPixmap(self._off_img))

    def flash(self, duration: int = 250) -> None:
        """Turns the LED on for a specified duration.

        Args:
            duration (int): Number of milliseconds to keep LED lit for
        """
        self.turn_on()
        self.timer.singleShot(duration, self.turn_off)
