from __future__ import annotations

from shared_py.exit_safety import ReduceOnlyExitRequest, build_exit_block_reasons_de, validate_emergency_flatten_request, validate_reduce_only_exit


def test_exit_qty_over_position_blocks() -> None:
    reasons = validate_reduce_only_exit(
        ReduceOnlyExitRequest("BTCUSDT", 2.0, 1.0, True, [50.0, 50.0], 0.1, True, None)
    )
    assert "exit_menge_ueber_position" in reasons


def test_reduce_only_missing_blocks() -> None:
    reasons = validate_reduce_only_exit(
        ReduceOnlyExitRequest("BTCUSDT", 0.5, 1.0, False, [100.0], 0.1, True, None)
    )
    assert "reduce_only_fehlt" in reasons


def test_emergency_flatten_does_not_open_new_position() -> None:
    reasons = validate_emergency_flatten_request(
        ReduceOnlyExitRequest("BTCUSDT", 1.2, 1.0, True, [100.0], 0.1, True, "kill_switch", True)
    )
    assert "emergency_flatten_wuerde_position_eroeffnen" in reasons


def test_tp_splits_over_100_blocks() -> None:
    reasons = validate_reduce_only_exit(
        ReduceOnlyExitRequest("BTCUSDT", 0.5, 1.0, True, [60.0, 50.0], 0.1, True, None)
    )
    assert "tp_split_ueber_100_prozent" in reasons


def test_cancel_replace_duplicate_block_reason_de() -> None:
    text = build_exit_block_reasons_de(["cancel_replace_duplicate"])
    assert any("Duplikatorder" in item for item in text)


def test_german_reasons_generated() -> None:
    text = build_exit_block_reasons_de(["reduce_only_fehlt"])
    assert any("Reduce-only fehlt" in item for item in text)
