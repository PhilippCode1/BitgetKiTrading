from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from shared_py.bitget.asset_universe import (
    BitgetAssetCatalogEntry,
    block_reasons_to_german,
    evaluate_live_block_reasons,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "refresh_bitget_asset_universe.py"
FIXTURE = ROOT / "tests" / "fixtures" / "bitget_asset_universe_sample.json"


def _entry(**overrides: object) -> BitgetAssetCatalogEntry:
    payload: dict[str, object] = {
        "symbol": "ETHUSDT",
        "base_coin": "ETH",
        "quote_coin": "USDT",
        "market_family": "futures",
        "product_type": "USDT-FUTURES",
        "margin_coin": "USDT",
        "status_on_exchange": "active",
        "chart_available": True,
        "trading_available": True,
        "paper_allowed": True,
        "shadow_allowed": True,
        "live_allowed": False,
        "tick_size": "0.1",
        "lot_size": "0.001",
        "min_qty": "0.001",
        "min_notional": "5",
        "price_precision": 1,
        "quantity_precision": 3,
        "funding_relevant": True,
        "open_interest_relevant": True,
        "last_metadata_refresh_ts": "2026-04-25T16:00:00+00:00",
        "metadata_source": "fixture",
        "risk_tier": "RISK_TIER_1_MAJOR_LIQUID",
        "liquidity_tier": "LIQUIDITY_TIER_1",
        "data_quality_status": "data_ok",
        "operator_note_de": "Regulaeres Asset",
    }
    payload.update(overrides)
    return BitgetAssetCatalogEntry.model_validate(payload)


def test_valid_futures_asset_recognized() -> None:
    out = _entry().with_evaluated_live_gate()
    assert out.symbol == "ETHUSDT"
    assert out.market_family == "futures"


def test_futures_without_product_type_live_blocked() -> None:
    reasons = evaluate_live_block_reasons(_entry(product_type=None))
    assert "futures_product_type_fehlt" in reasons


def test_futures_without_margin_coin_live_blocked() -> None:
    reasons = evaluate_live_block_reasons(_entry(margin_coin=None))
    assert "futures_margin_coin_fehlt" in reasons


def test_delisted_asset_live_blocked() -> None:
    reasons = evaluate_live_block_reasons(_entry(status_on_exchange="delisted"))
    assert "exchange_status_delisted" in reasons


def test_unknown_asset_live_blocked() -> None:
    reasons = evaluate_live_block_reasons(_entry(status_on_exchange="unknown"))
    assert "exchange_status_unknown" in reasons


def test_new_asset_not_automatically_live_allowed() -> None:
    entry = _entry(
        operator_note_de="Neues Asset in Beobachtung", live_allowed=True
    ).with_evaluated_live_gate()
    assert entry.live_allowed is False
    assert "neues_asset_nicht_automatisch_live" in entry.live_block_reasons


def test_new_asset_blocks_even_when_input_live_flag_is_false() -> None:
    entry = _entry(
        operator_note_de="Neu aufgenommen, vorerst shadow-only.", live_allowed=False
    ).with_evaluated_live_gate()
    assert entry.live_allowed is False
    assert "neues_asset_nicht_automatisch_live" in entry.live_block_reasons


def test_asset_without_tick_size_live_blocked() -> None:
    reasons = evaluate_live_block_reasons(_entry(tick_size=None))
    assert "tick_size_fehlt" in reasons


def test_asset_without_lot_size_live_blocked() -> None:
    reasons = evaluate_live_block_reasons(_entry(lot_size=None))
    assert "lot_size_fehlt" in reasons


def test_block_reasons_have_german_messages() -> None:
    de = block_reasons_to_german(["futures_product_type_fehlt", "lot_size_fehlt"])
    assert any("Futures-Asset" in item for item in de)
    assert any("Lot-Size" in item for item in de)


def test_refresh_script_reads_fixture_and_writes_reports(tmp_path: Path) -> None:
    out_json = tmp_path / "report.json"
    out_md = tmp_path / "report.md"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input-json",
            str(FIXTURE),
            "--output-json",
            str(out_json),
            "--output-md",
            str(out_md),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "refresh_bitget_asset_universe" in completed.stdout
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["total_assets"] >= 1
    assert "Asset-Universum" in out_md.read_text(encoding="utf-8")


def test_no_secrets_exposed_in_generated_report(tmp_path: Path) -> None:
    out_json = tmp_path / "report.json"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input-json",
            str(FIXTURE),
            "--output-json",
            str(out_json),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    content = out_json.read_text(encoding="utf-8").lower()
    assert "secret" not in content
    assert "password" not in content
    assert "token" not in content
