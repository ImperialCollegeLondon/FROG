"""Provides a collection of controls for editing a measure script."""

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from frog.config import ANGLE_PRESETS
from frog.gui.measure_script.count_widget import CountWidget
from frog.gui.measure_script.script import Measurement


class SequenceWidget(QWidget):
    """A widget with a table of measure instructions and controls to modify them."""

    def __init__(self, sequence: list[Measurement] | None = None) -> None:
        """Create a new SequenceWidget."""
        super().__init__()

        self.table = QTableView()

        self.sequence = sequence if sequence else []
        """The sequence of measure instructions as a list of angles and counts."""

        self.model = SequenceModel(self.sequence)
        self.table.setModel(self.model)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.buttons = SequenceButtons(self)

        # Put the table on the left and the buttons on the right
        layout = QHBoxLayout()
        layout.addWidget(self.table)
        layout.addWidget(self.buttons)
        self.setLayout(layout)

    def add_instruction(self, angle: str | float, measurements: int) -> None:
        """Add a new measure instruction to the sequence.

        Args:
            angle: Target angle as a float or a string corresponding to a preset
            measurements: Number of times to take a measurement at this angle
        """
        self.sequence.append(Measurement(angle, measurements))
        self.model.layoutChanged.emit()
        self.table.scrollToBottom()

    def _get_selected_rows(self, reverse: bool = False) -> list[int]:
        """Get the indices of the currently selected rows in the table.

        Args:
            reverse: Whether to return the indices in reverse order
        """
        selected = [idx.row() for idx in self.table.selectionModel().selectedRows()]
        selected.sort(reverse=reverse)
        return selected

    def _swap_rows(self, lower: int, higher: int) -> None:
        """Swap the rows specified by two indices."""
        # For some reason if these arguments are the wrong way round, Qt crashes
        assert higher > lower

        self.model.beginMoveRows(QModelIndex(), higher, higher, QModelIndex(), lower)
        self.sequence[lower], self.sequence[higher] = (
            self.sequence[higher],
            self.sequence[lower],
        )
        self.model.endMoveRows()

    def move_selected_up(self) -> None:
        """Move the currently selected instructions up one row."""
        selected = self._get_selected_rows()
        if not selected or selected[0] == 0:
            # We can't move up if the topmost item is selected
            return

        # Swap each element with the one above it
        for row in selected:
            self._swap_rows(row - 1, row)

    def move_selected_down(self) -> None:
        """Move the currently selected instructions down one row."""
        selected = self._get_selected_rows(reverse=True)
        if not selected or selected[0] == len(self.sequence) - 1:
            # We can't move down if the bottom item is selected
            return

        # Swap each element with the one below it
        for row in selected:
            self._swap_rows(row, row + 1)

    def delete_selected(self) -> None:
        """Remove the currently selected instructions from the table."""
        for row in self._get_selected_rows(reverse=True):
            self.model.beginRemoveRows(QModelIndex(), row, row)
            self.sequence.pop(row)
            self.model.endRemoveRows()

    def _confirm_delete_all(self) -> bool:
        """Confirm whether user wants to delete all instructions."""
        dlg = QMessageBox(
            QMessageBox.Icon.Question,
            "Clear all instructions?",
            "Are you sure you would like to clear all instructions?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            self,
        )
        return dlg.exec_() == QMessageBox.StandardButton.Yes

    def delete_all(self) -> None:
        """Delete all instructions from the table."""
        if self.sequence and self._confirm_delete_all():
            self.model.beginRemoveRows(QModelIndex(), 0, len(self.sequence) - 1)
            self.sequence.clear()
            self.model.endRemoveRows()


class SequenceModel(QAbstractTableModel):
    """Provides a model of the sequence data for the QTableView."""

    _COLUMNS = ("angle", "measurements")
    """The names of the data columns."""

    def __init__(self, sequence: list[Measurement]) -> None:
        """Create a new SequenceModel.

        Args:
            sequence: A list of Measurements
        """
        super().__init__()
        self._sequence = sequence

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Provides the model's data."""
        # Column 0 is angle, column 1 is measurements
        if role == Qt.ItemDataRole.DisplayRole:
            value = getattr(
                self._sequence[index.row()], SequenceModel._COLUMNS[index.column()]
            )
            if isinstance(value, float):
                return f"{value:.0f}°"
            return value

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Provides header names for the model's data."""
        # For column names we use Angle and Measurements
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return SequenceModel._COLUMNS[section].title()

        return super().headerData(section, orientation, role)

    def rowCount(self, *args: Any, **kwargs: Any) -> int:
        """Get the number of data rows."""
        return len(self._sequence)

    def columnCount(self, *args: Any, **kwargs: Any) -> int:
        """Get the number of data columns."""
        return 2


class SequenceButtons(QWidget):
    """Buttons for changing the sequence of instructions."""

    def __init__(self, sequence: SequenceWidget) -> None:
        """Create a new SequenceButtons."""
        super().__init__()

        add_buttons = AddButtons(sequence)
        change_buttons = ChangeButtons(sequence)

        layout = QVBoxLayout()
        layout.addWidget(add_buttons)
        layout.addWidget(change_buttons)
        self.setLayout(layout)


class AddButtons(QGroupBox):
    """Buttons for adding new instructions."""

    def __init__(self, sequence: SequenceWidget) -> None:
        """Create a new AddButtons."""
        super().__init__("Add instruction")
        self.sequence = sequence

        layout = QVBoxLayout()

        # The number of times to repeat this measurement
        self.count = CountWidget("Measurements")
        layout.addWidget(self.count)

        # Add buttons for preset angles (e.g. zenith, nadir, etc.)
        self.group = QButtonGroup()
        self.group.buttonClicked.connect(self._preset_clicked)
        for preset in ANGLE_PRESETS:
            btn = QPushButton(preset.upper())
            self.group.addButton(btn)
            layout.addWidget(btn)

        # Add button and spinbox for going to a specific angle. Put them next to each
        # other on the same row.
        goto_layout = QHBoxLayout()
        self.angle = QSpinBox()
        self.angle.setSuffix("°")
        self.angle.setMinimum(0)
        self.angle.setMaximum(270)
        self.goto = QPushButton("GOTO")
        self.goto.clicked.connect(self._goto_clicked)
        goto_layout.addWidget(self.angle)
        goto_layout.addWidget(self.goto)

        # Add these widgets to the main layout
        goto_widgets = QWidget()
        goto_widgets.setLayout(goto_layout)
        layout.addWidget(goto_widgets)

        self.setLayout(layout)

    def _goto_clicked(self) -> None:
        self.sequence.add_instruction(float(self.angle.value()), self.count.value())

    def _preset_clicked(self, btn: QPushButton) -> None:
        self.sequence.add_instruction(btn.text().lower(), self.count.value())


class ChangeButtons(QGroupBox):
    """Buttons for modifying existing measure instructions."""

    def __init__(self, sequence: SequenceWidget) -> None:
        """Create a new ChangeButtons."""
        super().__init__("Modify instructions")

        self.up = QPushButton("Up")
        self.up.clicked.connect(sequence.move_selected_up)

        self.down = QPushButton("Down")
        self.down.clicked.connect(sequence.move_selected_down)

        self.delete = QPushButton("Delete")
        self.delete.clicked.connect(sequence.delete_selected)

        self.clear = QPushButton("Clear")
        self.clear.clicked.connect(sequence.delete_all)

        layout = QVBoxLayout()
        layout.addWidget(self.up)
        layout.addWidget(self.down)
        layout.addWidget(self.delete)
        layout.addWidget(self.clear)
        self.setLayout(layout)
