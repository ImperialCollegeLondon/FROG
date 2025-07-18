"""Provides a widget with a labelled QSpinBox.

Used in ScriptEditDialog in a couple of places.
"""

from PySide6.QtWidgets import QFormLayout, QSpinBox, QWidget


class CountWidget(QWidget):
    """A widget with labelled QSpinBox."""

    def __init__(self, label: str, initial_count: int = 1) -> None:
        """Create a new CountWidget.

        Args:
            label: A string label for the control
            initial_count: The initial value of the QSpinBox
        """
        super().__init__()

        self.count = QSpinBox()
        self.count.setMinimum(1)
        self.count.setMaximum(9999)
        self.count.setValue(initial_count)

        layout = QFormLayout()
        layout.addRow(f"{label}:", self.count)
        self.setLayout(layout)

    def value(self) -> int:
        """Get the value of the QSpinBox."""
        return self.count.value()
