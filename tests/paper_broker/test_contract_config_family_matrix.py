from __future__ import annotations

import sys
from pathlib import Path
from decimal import Decimal

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PAPER_BROKER_SRC = REPO_ROOT / "services" / "paper-broker" / "src"
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for candidate in (REPO_ROOT, PAPER_BROKER_SRC, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from paper_broker.config import PaperBrokerSettings
from paper_broker.engine.contract_config import ContractConfigProvider
from tests.fixtures.family_runtime_matrix import FAMILY_RUNTIME_CASES, catalog_entry_for_case


def _settings_for_case(case: dict) -> PaperBrokerSettings:
    return PaperBrokerSettings.model_construct(
        paper_contract_config_mode="fixture",
        bitget_api_base_url="https://api.bitget.com",
        bitget_market_family=case["market_family"],
        bitget_margin_account_mode=case["margin_account_mode"],
        bitget_product_type=case["product_type"] or "USDT-FUTURES",
        paper_default_maker_fee="0.0002",
        paper_default_taker_fee="0.0006",
        paper_max_leverage=75,
    )


@pytest.mark.parametrize("case", FAMILY_RUNTIME_CASES, ids=[c["name"] for c in FAMILY_RUNTIME_CASES])
def test_contract_config_parse_matrix_by_family(case: dict) -> None:
    settings = _settings_for_case(case)
    provider = ContractConfigProvider(settings)
    entry = catalog_entry_for_case(case)
    payload = {
        "symbol": case["symbol"],
        "productType": case["product_type"],
        "makerFeeRate": case["maker_fee_rate"],
        "takerFeeRate": case["taker_fee_rate"],
        "sizeMultiplier": case["size_multiplier"],
        "fundInterval": str(case["fund_interval_hours"]),
        "maxLever": str(case["max_lever"]),
        "priceEndStep": case["price_end_step"],
    }

    view = provider._parse_dict(payload, case["symbol"], entry=entry)

    expected_product = case["product_type"] if case["market_family"] == "futures" else case["market_family"].upper()
    assert view.symbol == case["symbol"].upper()
    assert view.product_type == expected_product
    assert view.maker_fee_rate == Decimal(case["maker_fee_rate"])
    assert view.taker_fee_rate == Decimal(case["taker_fee_rate"])
    assert view.size_multiplier == Decimal(case["size_multiplier"])
    assert view.fund_interval_hours == case["fund_interval_hours"]
    assert view.max_lever == case["max_lever"]
    assert view.price_end_step == Decimal(case["price_end_step"])


def test_contract_config_fixture_loads_ethusdt_json_not_only_btc_fallback() -> None:
    settings = PaperBrokerSettings.model_construct(
        paper_contract_config_mode="fixture",
        bitget_api_base_url="https://api.bitget.com",
        bitget_market_family="futures",
        bitget_margin_account_mode="isolated",
        bitget_product_type="USDT-FUTURES",
        paper_default_maker_fee="0.0002",
        paper_default_taker_fee="0.0006",
        paper_max_leverage=75,
    )
    provider = ContractConfigProvider(settings)
    view = provider._from_fixture("ETHUSDT")
    assert view.symbol == "ETHUSDT"
    assert view.price_end_step == Decimal("0.01")


def test_contract_config_defaults_futures_interval_and_spot_leverage() -> None:
    fut_case = next(case for case in FAMILY_RUNTIME_CASES if case["name"] == "futures_btcusdt_usdt")
    spot_case = next(case for case in FAMILY_RUNTIME_CASES if case["name"] == "spot_btcusdt")

    fut = ContractConfigProvider(_settings_for_case(fut_case))._parse_dict(
        {"symbol": fut_case["symbol"]},
        fut_case["symbol"],
        entry=catalog_entry_for_case(fut_case),
    )
    spot = ContractConfigProvider(_settings_for_case(spot_case))._parse_dict(
        {"symbol": spot_case["symbol"], "pricePrecision": "0.01"},
        spot_case["symbol"],
        entry=catalog_entry_for_case(spot_case),
    )

    assert fut.fund_interval_hours == 8
    assert spot.fund_interval_hours == 0
    assert spot.max_lever == 1


def test_contract_config_live_fetch_falls_back_to_fixture_in_local(monkeypatch) -> None:
    fut_case = next(case for case in FAMILY_RUNTIME_CASES if case["name"] == "futures_btcusdt_usdt")
    settings = PaperBrokerSettings.model_construct(
        production=False,
        app_env="local",
        paper_contract_config_mode="live",
        bitget_api_base_url="https://api.bitget.com",
        bitget_market_family="futures",
        bitget_margin_account_mode="isolated",
        bitget_product_type="USDT-FUTURES",
        paper_default_maker_fee="0.0002",
        paper_default_taker_fee="0.0006",
        paper_max_leverage=75,
    )

    class _BoomClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr("paper_broker.engine.contract_config.httpx.Client", lambda *a, **k: _BoomClient())
    provider = ContractConfigProvider(settings)
    view = provider.get(fut_case["symbol"])
    assert view.symbol == fut_case["symbol"]


def test_contract_config_live_fetch_fails_closed_in_shadow(monkeypatch) -> None:
    fut_case = next(case for case in FAMILY_RUNTIME_CASES if case["name"] == "futures_btcusdt_usdt")
    settings = PaperBrokerSettings.model_construct(
        production=True,
        app_env="shadow",
        paper_contract_config_mode="live",
        bitget_api_base_url="https://api.bitget.com",
        bitget_market_family="futures",
        bitget_margin_account_mode="isolated",
        bitget_product_type="USDT-FUTURES",
        paper_default_maker_fee="0.0002",
        paper_default_taker_fee="0.0006",
        paper_max_leverage=75,
    )

    class _BoomClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr("paper_broker.engine.contract_config.httpx.Client", lambda *a, **k: _BoomClient())
    provider = ContractConfigProvider(settings)
    with pytest.raises(RuntimeError, match="prod-like mode"):
        provider.get(fut_case["symbol"])
