from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared_py.eventbus.payload_schemas import (
    SchemaValidationError,
    ensure_payload_matches_schema,
)
from shared_py.signal_contracts import (
    BotParams,
    ExecutionMode,
    PayloadSignalCreated,
)


def test_payload_signal_created_standard_futures_valid() -> None:
    """
    Verifiziert, dass STANDARD_FUTURES Signale ohne bot_params valide sind.
    """
    payload = PayloadSignalCreated(
        signal_id="sig_test_123",
        direction="long",
        market_regime="bullish_expansion",
        regime_bias="long",
        regime_confidence_0_1=0.85,
        signal_strength_0_100=75.5,
        probability_0_1=0.78,
        execution_mode=ExecutionMode.STANDARD_FUTURES,
        leverage_cap_applied=False,
    )
    assert payload.signal_id == "sig_test_123"
    assert payload.execution_mode == ExecutionMode.STANDARD_FUTURES
    assert payload.bot_params is None
    assert payload.leverage_cap_applied is False

    # JSON-Schema-Validierung (End-to-End)
    ensure_payload_matches_schema("signal_created", payload.model_dump(mode="json"))


def test_payload_signal_created_bot_grid_valid() -> None:
    """
    Verifiziert, dass BOT_GRID Signale mit korrekten bot_params valide sind.
    """
    bot_params = BotParams(
        upper_bound=95000.0,
        lower_bound=85000.0,
        grid_count=50,
        trailing_enabled=True,
    )
    payload = PayloadSignalCreated(
        signal_id="sig_bot_456",
        direction="short",
        execution_mode=ExecutionMode.BOT_GRID,
        bot_params=bot_params,
        leverage_cap_applied=True,
    )
    assert payload.signal_id == "sig_bot_456"
    assert payload.execution_mode == ExecutionMode.BOT_GRID
    assert payload.bot_params is not None
    assert payload.bot_params.upper_bound == 95000.0
    assert payload.bot_params.lower_bound == 85000.0
    assert payload.bot_params.grid_count == 50
    assert payload.bot_params.trailing_enabled is True
    assert payload.leverage_cap_applied is True

    # JSON-Schema-Validierung (End-to-End)
    ensure_payload_matches_schema("signal_created", payload.model_dump(mode="json"))


def test_payload_signal_created_bot_dca_valid() -> None:
    """
    Verifiziert, dass BOT_DCA Signale mit korrekten bot_params valide sind.
    """
    bot_params = BotParams(
        upper_bound=100.0,
        lower_bound=50.0,
        grid_count=10,
        trailing_enabled=False,
    )
    payload = PayloadSignalCreated(
        signal_id="sig_bot_789",
        direction="neutral",
        execution_mode=ExecutionMode.BOT_DCA,
        bot_params=bot_params,
        leverage_cap_applied=False,
    )
    assert payload.execution_mode == ExecutionMode.BOT_DCA
    assert payload.bot_params is not None

    # JSON-Schema-Validierung (End-to-End)
    ensure_payload_matches_schema("signal_created", payload.model_dump(mode="json"))


def test_payload_signal_created_bot_without_params_raises_validation_error() -> None:
    """
    Stellt sicher, dass bei BOT_GRID/BOT_DCA ohne bot_params eine ValidationError geworfen wird.
    """
    # 1. Pydantic-Ebene
    with pytest.raises(ValidationError) as exc_info:
        PayloadSignalCreated(
            signal_id="sig_invalid",
            direction="long",
            execution_mode=ExecutionMode.BOT_GRID,
            bot_params=None,
            leverage_cap_applied=False,
        )
    assert "bot_params" in str(exc_info.value)

    # 2. JSON-Schema-Ebene (direkt mit ungueltigen Rohdaten testen)
    invalid_raw_payload = {
        "signal_id": "sig_invalid",
        "direction": "long",
        "execution_mode": "BOT_GRID",
        "bot_params": None,
        "leverage_cap_applied": False,
    }
    with pytest.raises(SchemaValidationError):
        ensure_payload_matches_schema("signal_created", invalid_raw_payload)


def test_bot_params_bounds_validation() -> None:
    """
    Verifiziert, dass upper_bound strikt groesser als lower_bound sein muss.
    """
    with pytest.raises(ValidationError) as exc_info:
        BotParams(
            upper_bound=50000.0,
            lower_bound=50000.0,  # Gleich
            grid_count=20,
            trailing_enabled=False,
        )
    assert "upper_bound" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        BotParams(
            upper_bound=40000.0,
            lower_bound=50000.0,  # Upper kleiner als Lower
            grid_count=20,
            trailing_enabled=False,
        )
    assert "upper_bound" in str(exc_info.value)


def test_bot_params_grid_count_validation() -> None:
    """
    Verifiziert, dass grid_count im Bereich [2, 500] liegen muss.
    """
    with pytest.raises(ValidationError):
        BotParams(
            upper_bound=10.0,
            lower_bound=5.0,
            grid_count=1,  # Zu klein
            trailing_enabled=False,
        )

    with pytest.raises(ValidationError):
        BotParams(
            upper_bound=10.0,
            lower_bound=5.0,
            grid_count=501,  # Zu gross
            trailing_enabled=False,
        )


def test_json_schema_violating_inputs() -> None:
    """
    Testet fehlerhafte Signale direkt gegen das JSON-Schema, um die Unumstoesslichkeit abzusichern.
    """
    # Rueckwaertskompatibilitaet: execution_mode und leverage_cap_applied werden automatisch ergaenzt
    legacy_payload = {
        "signal_id": "sig_incomplete",
        "direction": "long",
    }
    ensure_payload_matches_schema("signal_created", legacy_payload)
    assert legacy_payload["execution_mode"] == "STANDARD_FUTURES"
    assert legacy_payload["leverage_cap_applied"] is False

    # Fehlende Kern-Pflichtfelder (signal_id) muessen weiterhin scheitern
    missing_core_payload = {
        "direction": "long",
        "execution_mode": "STANDARD_FUTURES",
        "leverage_cap_applied": False,
    }
    with pytest.raises(SchemaValidationError):
        ensure_payload_matches_schema("signal_created", missing_core_payload)

    # Ungueltiger execution_mode
    invalid_mode_payload = {
        "signal_id": "sig_invalid",
        "direction": "long",
        "execution_mode": "INVALID_MODE",
        "leverage_cap_applied": False,
    }
    with pytest.raises(SchemaValidationError):
        ensure_payload_matches_schema("signal_created", invalid_mode_payload)

    # Ungueltige bot_params Typen
    bad_types_payload = {
        "signal_id": "sig_bad_types",
        "direction": "long",
        "execution_mode": "BOT_GRID",
        "leverage_cap_applied": False,
        "bot_params": {
            "upper_bound": "not-a-float",
            "lower_bound": 10.0,
            "grid_count": 50,
            "trailing_enabled": True,
        },
    }
    with pytest.raises(SchemaValidationError):
        ensure_payload_matches_schema("signal_created", bad_types_payload)
