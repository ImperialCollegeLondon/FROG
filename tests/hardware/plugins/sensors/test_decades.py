"""Tests for the Decades class."""

import json
from collections.abc import Sequence
from itertools import chain, combinations, product
from unittest.mock import MagicMock, Mock, patch

import pytest
from freezegun import freeze_time

from frog.config import DECADES_URL
from frog.hardware.plugins.sensors.decades import (
    Decades,
    DecadesParameter,
    _get_selected_params,
)
from frog.sensor_reading import SensorReading


@pytest.fixture
@patch("frog.hardware.plugins.sensors.decades.HTTPRequester")
def decades(requester_mock, qtbot, subscribe_mock) -> Decades:
    """Fixture for Decades."""
    return Decades()


@pytest.mark.parametrize("params", ((), ("a"), ("a", "b")))
def test_init(params: Sequence[str], qtbot) -> None:
    """Test the Decades constructor."""
    with patch.object(Decades, "obtain_parameter_list") as obtain_params:
        sensors = Decades("1.2.3.4", 2.0, ",".join(params))
        assert sensors._url == DECADES_URL.format(host="1.2.3.4")
        obtain_params.assert_called_once_with(frozenset(params))


PARAMS = [DecadesParameter("a", "A", "m"), DecadesParameter("b", "B", "J")]
"""Example parameters."""


@patch("json.loads")
@patch("frog.hardware.plugins.sensors.decades.Decades._get_decades_data")
def test_handle_response(
    get_decades_data_mock: Mock, json_loads_mock: Mock, decades: Decades
) -> None:
    """Test the handle_response() method processes sensor readings correctly."""
    response = "RESPONSE"
    get_decades_data_mock.return_value = range(3)

    # Check send_readings_message() is called
    with patch.object(decades, "send_readings_message") as send_readings_mock:
        decades.handle_response(response)
        send_readings_mock.assert_called_once_with((0, 1, 2))
        json_loads_mock.assert_called_once_with(response)


def test_obtain_parameter_list(decades: Decades) -> None:
    """Tests the obtain_parameter_list() method."""
    with patch.object(decades, "make_request") as make_request_mock:
        with patch.object(decades, "_on_params_received") as params_received_mock:
            params = MagicMock()
            decades.obtain_parameter_list(params)
            make_request_mock.assert_called_once()

            params_received_mock.assert_not_called()
            reply = MagicMock()
            make_request_mock.call_args.args[1](reply)
            params_received_mock.assert_called_once_with(reply, params=params)


@pytest.mark.parametrize("params", (set(), set("ab")))
def test_on_params_received(params: set[str], decades: Decades) -> None:
    """Test the _on_params_received() method."""
    assert not hasattr(decades, "_params")
    all_params_info = (
        {
            "ParameterName": "a",
            "DisplayText": "A",
            "DisplayUnits": "m",
            "available": True,
        },
        {
            "ParameterName": "b",
            "DisplayText": "B",
            "DisplayUnits": "J",
            "available": True,
        },
        {
            "ParameterName": "c",
            "DisplayText": "C",
            "DisplayUnits": "V",
            "available": False,
        },
    )
    response = json.dumps(all_params_info)

    with patch.object(decades, "start_polling") as start_mock:
        decades._on_params_received(response, params)
        assert decades._params == [p for p in PARAMS if not params or p.name in params]
        start_mock.assert_called_once_with()


@freeze_time("1970-01-01 00:01:00")
def test_request_readings(decades: Decades) -> None:
    """Tests the request_readings() method."""
    decades._params = PARAMS
    with patch.object(decades, "make_request") as make_request_mock:
        decades.request_readings()
        query = decades._url + "/livedata?&frm=60&to=60&para=a&para=b"
        make_request_mock.assert_called_once_with(query)


@patch("frog.hardware.plugins.sensors.decades.logging.warn")
def test_get_decades_data(warn_mock: Mock, decades: Decades) -> None:
    """Tests the get_decades_data() function on normal data."""
    decades._params = PARAMS
    data = tuple(decades._get_decades_data({"a": [1.0], "b": [2.0]}))
    assert data == (SensorReading("A", 1.0, "m"), SensorReading("B", 2.0, "J"))
    warn_mock.assert_not_called()


@patch("frog.hardware.plugins.sensors.decades.logging.warn")
def test_get_decades_data_missing(warn_mock: Mock, decades: Decades) -> None:
    """Tests the get_decades_data() function for when there are missing data."""
    params = [
        DecadesParameter("a", "A", "m"),
        DecadesParameter("b", "B", "J"),
        DecadesParameter("c", "C", "V"),
    ]
    decades._params = params
    data = tuple(decades._get_decades_data({"a": [1.0], "b": [2.0]}))
    assert data == (SensorReading("A", 1.0, "m"), SensorReading("B", 2.0, "J"))
    warn_mock.assert_called_once()


@pytest.mark.parametrize(
    "params,available",
    product(
        chain.from_iterable(
            (set(c) for c in combinations("ab", n)) for n in range(1, 3)
        ),
        chain.from_iterable(
            (set(c) for c in combinations("ab", n)) for n in range(0, 3)
        ),
    ),
)
def test_get_selected_params(params: set[str], available: set[str]) -> None:
    """Test the _get_selected_params() function."""
    all_params_info = (
        {
            "ParameterName": "a",
            "DisplayText": "A",
            "DisplayUnits": "m",
            "available": False,
        },
        {
            "ParameterName": "b",
            "DisplayText": "B",
            "DisplayUnits": "J",
            "available": False,
        },
    )
    for param_info in all_params_info:
        param_info["available"] = param_info["ParameterName"] in available

    params_out = tuple(_get_selected_params(all_params_info, params))
    assert params_out == tuple(
        map(
            DecadesParameter.from_dict,
            (
                p
                for p in all_params_info
                if p["ParameterName"] in params and p["available"]
            ),
        )
    )


@patch("frog.hardware.plugins.sensors.decades.logging")
def test_get_selected_params_missing(logging_mock: Mock) -> None:
    """Test the _get_selected_params() function when one parameter is missing."""
    all_params_info = (
        {
            "ParameterName": "a",
            "DisplayText": "A",
            "DisplayUnits": "m",
            "available": True,
        },
        {
            "ParameterName": "b",
            "DisplayText": "B",
            "DisplayUnits": "J",
            "available": True,
        },
        {
            "ParameterName": "c",
            "DisplayText": "C",
            "DisplayUnits": "V",
            "available": True,
        },
    )
    params = set("ad")
    params_out = tuple(_get_selected_params(all_params_info, params))
    assert params_out == (DecadesParameter.from_dict(all_params_info[0]),)
    logging_mock.warn.assert_called_once()
