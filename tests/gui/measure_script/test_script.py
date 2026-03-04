"""Tests for the measure script code."""

from contextlib import nullcontext as does_not_raise
from itertools import chain
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
import yaml
from PySide6.QtWidgets import QWidget

from frog.config import ANGLE_PRESET_NAMES
from frog.gui.measure_script.script import (
    CURRENT_SCRIPT_VERSION,
    Measurement,
    ParseError,
    Script,
    parse_script,
)


def is_valid_angle(angle: Any) -> bool:
    """Check whether the angle is valid."""
    if isinstance(angle, float) and 0.0 <= angle < 360.0:
        return True

    if angle in ANGLE_PRESET_NAMES:
        return True

    return False


def get_data(repeats: int, angle: Any, num_attributes: int) -> dict[str, Any]:
    """Get all or part of data script.

    Passing angle==() allows for testing with an empty sequence.
    """
    if angle == ():
        angles = []
    else:
        angles = [
            {"angle": angle, "measurements": 1},
            {"angle": 4.0, "measurements": 1},
        ]
    data = {
        "repeats": repeats,
        "sequence": angles,
        "version": CURRENT_SCRIPT_VERSION,
        "extra_attribute": "hello",
    }

    return {k: data[k] for k in list(data.keys())[:num_attributes]}


@pytest.mark.parametrize(
    "data,raises",
    [
        (
            get_data(repeats, angle, num_attributes),
            does_not_raise()
            if repeats > 0 and is_valid_angle(angle) and 2 <= num_attributes <= 3
            else pytest.raises(ParseError),
        )
        for repeats in range(-5, 5)
        for angle in chain(
            (float(i) for i in range(-180, 541, 60)),
            (4, "nadir", "NADIR", "badger", "kevin", "", ()),
        )
        for num_attributes in range(4)
    ],
)
def test_parse_script(data: dict[str, Any], raises: Any) -> None:
    """Check that errors are thrown for invalid data.

    Note that we don't check that serialisation and deserialisation work correctly as it
    is assumed that PyYAML is doing this correctly.
    """
    with raises:
        parse_script(yaml.safe_dump(data))


_SCRIPT_PATH = Path(__file__).parent / "test_script.yaml"


def test_try_load_success(qtbot) -> None:
    """Test the try_load() function."""
    script = Script.try_load(QWidget(), _SCRIPT_PATH)
    assert script, "Script could not be loaded"

    assert script.repeats == 1
    assert len(script.sequence) == 2
    assert script.sequence[0] == Measurement("zenith", 1)
    assert script.sequence[1] == Measurement(0.0, 1)


@pytest.mark.parametrize(
    "exception,raises",
    (
        (OSError(), does_not_raise()),
        (ParseError(), does_not_raise()),
        (Exception(), pytest.raises(Exception)),
    ),
)
@patch("frog.gui.measure_script.script.show_error_message")
def test_try_load_fail(
    show_error_mock: Any, exception: BaseException, raises: Any, qtbot
) -> None:
    """Test the try_load() function."""
    with patch("frog.gui.measure_script.script.parse_script", side_effect=exception):
        with raises:
            script = Script.try_load(QWidget(), _SCRIPT_PATH)
            assert script is None, "Script should not have been loaded"
            show_error_mock.assert_called_once()


_MEASUREMENTS = [Measurement(float(i), i) for i in range(1, 4)]


@pytest.mark.parametrize(
    "num_measurements,repeats",
    (
        (num_measurements, repeats)
        for num_measurements in range(1, 4)
        for repeats in range(1, 4)
    ),
)
def test_script_iterator(num_measurements: int, repeats: int) -> None:
    """Test the ScriptIterator class."""
    script = Script(Path(), repeats, [])
    script.sequence = _MEASUREMENTS[:num_measurements]
    it = iter(script)
    assert it.current_repeat == 0

    # Check that we get the correct values "repeats" times
    with does_not_raise():
        for i in range(repeats):
            assert all(next(it) == m for m in script.sequence)
            assert it.current_repeat == i

    # Check that we get a StopIteration at the end
    with pytest.raises(StopIteration):
        next(it)
        assert it.current_repeat == repeats

    # Check that calling it again still yields an error!
    with pytest.raises(StopIteration):
        next(it)
        assert it.current_repeat == repeats


@patch("frog.gui.measure_script.script.ScriptRunner")
def test_script_run(script_runner_mock: Mock) -> None:
    """Test Script's run() method."""
    mock2 = MagicMock()
    script_runner_mock.return_value = mock2
    script = Script(Path(), 1, ())
    script.run()
    script_runner_mock.assert_called_once()
    mock2.start_moving.assert_called_once()
