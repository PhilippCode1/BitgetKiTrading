from __future__ import annotations

from typing import Any

from shared_py.model_contracts import stable_json_hash


def compute_data_version_hash(
    *,
    symbol: str | None,
    paper_trade_ids: list[str],
    decision_ts_ms: list[int],
    label_digest: list[Any],
    feature_schema_hash: str,
) -> str:
    return stable_json_hash(
        {
            "symbol": symbol.upper() if symbol else None,
            "paper_trade_ids": paper_trade_ids,
            "decision_ts_ms": decision_ts_ms,
            "label_digest": label_digest,
            "feature_schema_hash": feature_schema_hash,
        }
    )
