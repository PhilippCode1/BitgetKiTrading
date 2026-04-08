from __future__ import annotations

from shared_py.model_registry_policy import (
    champion_assignment_calibration_ok,
    model_requires_probability_calibration,
    parse_metadata_json,
    production_probability_calibration_satisfied,
)
from shared_py.take_trade_model import TAKE_TRADE_MODEL_NAME


def test_take_trade_requires_calibration() -> None:
    assert model_requires_probability_calibration(TAKE_TRADE_MODEL_NAME) is True


def test_regression_not_requiring_calibration() -> None:
    assert model_requires_probability_calibration("expected_return_bps") is False


def test_production_calibration_sigmoid_ok() -> None:
    assert (
        production_probability_calibration_satisfied(
            model_name=TAKE_TRADE_MODEL_NAME,
            calibration_method="sigmoid",
            metadata_json={},
        )
        is True
    )


def test_production_calibration_invalid_method_string() -> None:
    assert (
        production_probability_calibration_satisfied(
            model_name=TAKE_TRADE_MODEL_NAME,
            calibration_method="platt",
            metadata_json={},
        )
        is False
    )


def test_production_calibration_missing_method() -> None:
    assert (
        production_probability_calibration_satisfied(
            model_name=TAKE_TRADE_MODEL_NAME,
            calibration_method=None,
            metadata_json={},
        )
        is False
    )


def test_parse_metadata_json() -> None:
    assert parse_metadata_json(None) == {}
    assert parse_metadata_json({"a": 1}) == {"a": 1}
    assert parse_metadata_json('{"b": 2}') == {"b": 2}
    assert parse_metadata_json("x") == {}
    assert parse_metadata_json("[1]") == {}


def test_production_calibration_isotonic_and_artifacts() -> None:
    assert (
        production_probability_calibration_satisfied(
            model_name=TAKE_TRADE_MODEL_NAME,
            calibration_method="isotonic",
            metadata_json={"artifact_files": {"calibration": "c.pkl"}},
        )
        is True
    )
    assert (
        production_probability_calibration_satisfied(
            model_name=TAKE_TRADE_MODEL_NAME,
            calibration_method="sigmoid",
            metadata_json={"calibration_method": "Isotonic"},
        )
        is True
    )


def test_champion_assignment_respects_flag() -> None:
    assert (
        champion_assignment_calibration_ok(
            model_name=TAKE_TRADE_MODEL_NAME,
            calibration_required=False,
            calibration_method=None,
            metadata_json={},
        )
        is True
    )
    assert (
        champion_assignment_calibration_ok(
            model_name=TAKE_TRADE_MODEL_NAME,
            calibration_required=True,
            calibration_method=None,
            metadata_json={},
        )
        is False
    )
