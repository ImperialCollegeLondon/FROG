"""Tests for the SequenceWidget class and other associated classes."""

from collections.abc import Sequence
from itertools import chain
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QPushButton

from frog.config import ANGLE_PRESETS
from frog.gui.measure_script.script import Measurement
from frog.gui.measure_script.sequence_widget import (
    AddButtons,
    ChangeButtons,
    SequenceWidget,
)


@pytest.fixture()
def widget(qtbot) -> SequenceWidget:
    """Test fixture for SequenceWidget."""
    return SequenceWidget()


def test_init(qtbot) -> None:
    """Check SequenceWidget's constructor."""
    widget = SequenceWidget()
    assert widget.sequence == []

    measurements = [Measurement(90.0, 3)]
    widget = SequenceWidget(measurements)
    assert widget.sequence == measurements


def test_add_instruction(widget: SequenceWidget, qtbot) -> None:
    """Test the add_instruction() method."""
    with qtbot.waitSignal(widget.model.layoutChanged):
        widget.add_instruction(90.0, 3)
        assert len(widget.sequence) == 1 and widget.sequence[0] == Measurement(90.0, 3)


_NO_SELECTION = ((i, (), range(i)) for i in range(4))
"""If no elements are selected, we expect the order won't change."""


def _swap_positions(seq: Sequence[int], i: int, j: int) -> Sequence[int]:
    lst = list(seq)
    lst[i], lst[j] = lst[j], lst[i]
    return lst


def _test_modify_rows_method(
    count: int,
    selected: Sequence[int],
    expected_after: Sequence[int],
    widget: SequenceWidget,
    func_name: str,
) -> None:
    """Check that the specified method modifies rows in the expected way."""
    for i in range(count):
        widget.add_instruction(float(i), i)

    for sel in selected:
        widget.table.selectRow(sel)

    # Modify rows
    getattr(widget, func_name)()

    # Sanity check that the measurements are as we expect
    assert all(seq.angle == seq.measurements for seq in widget.sequence)

    # Check that the final order is correct
    actual = [seq.measurements for seq in widget.sequence]
    expected = list(expected_after)
    assert actual == expected


@pytest.mark.parametrize(
    "count,selected,expected_after",
    chain(
        _NO_SELECTION,
        ((n, (0,), range(n)) for n in range(1, 4)),  # top row selected
        (
            (n, (i,), _swap_positions(range(n), i - 1, i))
            for n in range(1, 4)
            for i in range(1, n)
        ),
    ),
)
def test_move_selected_up(
    count: int,
    selected: Sequence[int],
    expected_after: Sequence[int],
    widget: SequenceWidget,
) -> None:
    """Test the move_selected_up() method."""
    _test_modify_rows_method(
        count, selected, expected_after, widget, "move_selected_up"
    )


@pytest.mark.parametrize(
    "count,selected,expected_after",
    chain(
        _NO_SELECTION,
        ((n, (n - 1,), range(n)) for n in range(1, 4)),  # bottom row selected
        (
            (n, (i,), _swap_positions(range(n), i, i + 1))
            for n in range(1, 4)
            for i in range(0, n - 1)
        ),
    ),
)
def test_move_selected_down(
    count: int,
    selected: Sequence[int],
    expected_after: Sequence[int],
    widget: SequenceWidget,
) -> None:
    """Test the move_selected_down() method."""
    _test_modify_rows_method(
        count, selected, expected_after, widget, "move_selected_down"
    )


def _list_without(idx: int, count: int) -> Sequence[int]:
    lst = list(range(count))
    lst.pop(idx)
    return lst


@pytest.mark.parametrize(
    "count,selected,expected_after",
    chain(
        _NO_SELECTION,
        ((n, (i,), _list_without(i, n)) for n in range(1, 4) for i in range(n)),
    ),
)
def test_delete_selected(
    count: int,
    selected: Sequence[int],
    expected_after: Sequence[int],
    widget: SequenceWidget,
) -> None:
    """Test the delete_selected() method."""
    _test_modify_rows_method(count, selected, expected_after, widget, "delete_selected")


@pytest.mark.parametrize(
    "count,confirmed",
    ((n, confirmed) for n in range(4) for confirmed in (True, False)),
)
def test_delete_all(count: int, confirmed: bool, widget: SequenceWidget) -> None:
    """Test the delete_all() method."""
    for i in range(count):
        widget.add_instruction(float(i), i)

    # Sanity check that the measurements are as we expect
    assert all(seq.angle == seq.measurements for seq in widget.sequence)

    # Patching QMessageBox directly didn't work for me, so just patch this method
    with patch.object(widget, "_confirm_delete_all") as confirm_mock:
        confirm_mock.return_value = confirmed
        widget.delete_all()

    # Check that all elements have been deleted iff confirmed
    actual = [seq.measurements for seq in widget.sequence]
    expected = list(range(count)) if not confirmed else []
    assert actual == expected


@pytest.mark.parametrize(
    "name,callee",
    (
        ("up", "move_selected_up"),
        ("down", "move_selected_down"),
        ("delete", "delete_selected"),
        ("clear", "delete_all"),
    ),
)
def test_change_buttons(name: str, callee: str, widget: SequenceWidget) -> None:
    """Test the ChangeButtons class."""
    with patch.object(widget, callee) as callee_mock:
        buttons = ChangeButtons(widget)
        button: QPushButton = getattr(buttons, name)

        # Check that the button is labelled as expected
        assert button.text() == name.capitalize()

        # Check that clicking the button triggers the right method
        button.click()
        callee_mock.assert_called_once()


@pytest.mark.parametrize(
    "preset,count",
    ((preset, count) for preset in ANGLE_PRESETS for count in range(1, 3)),
)
def test_add_buttons(preset: str, count: int, widget: SequenceWidget) -> None:
    """Test the AddButtons class."""
    buttons = AddButtons(widget)

    button = None
    try:
        button = next(
            btn for btn in buttons.group.buttons() if btn.text() == preset.upper()
        )
    except StopIteration:
        pass
    assert button

    buttons.count.count.setValue(count)
    with patch.object(widget, "add_instruction") as add_mock:
        button.click()
        add_mock.assert_called_once_with(preset, count)


@pytest.mark.parametrize(
    "angle,count",
    (
        (angle, count)
        for angle in (-90, 0, 1, 90, 180, 270, 359, 360)
        for count in range(1, 4)
    ),
)
def test_add_buttons_goto(angle: int, count: int, widget: SequenceWidget) -> None:
    """Test the GOTO button in the AddButtons panel."""
    LIMS = (0, 359)
    buttons = AddButtons(widget)

    buttons.angle.setValue(angle)
    buttons.count.count.setValue(count)
    with patch.object(widget, "add_instruction") as add_mock:
        buttons.goto.click()
        clamped_angle = max(LIMS[0], min(LIMS[1], angle))
        add_mock.assert_called_once_with(float(clamped_angle), count)
