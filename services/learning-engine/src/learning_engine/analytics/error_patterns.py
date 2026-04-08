from __future__ import annotations

import json
from collections import Counter
from typing import Any

from shared_py.model_contracts import extract_primary_feature_snapshot, normalize_market_regime


def _parse_labels(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for x in raw:
        if x is None:
            continue
        s = str(x).strip().upper()
        if s:
            out.append(s)
    return out


def pattern_key_from_labels(labels: list[str]) -> str:
    if not labels:
        return "__no_labels__"
    return "|".join(sorted(set(labels)))


def aggregate_error_patterns(
    rows: list[dict[str, Any]], *, max_examples: int = 5
) -> list[dict[str, Any]]:
    """Deterministische Pattern-Zählung über alle Trades."""
    buckets: dict[str, list[str]] = {}
    counts: Counter[str] = Counter()
    for r in rows:
        labels = _parse_labels(r.get("error_labels_json"))
        key = pattern_key_from_labels(labels)
        counts[key] += 1
        pid = str(r.get("paper_trade_id", ""))
        if pid and key not in buckets:
            buckets[key] = []
        if pid and len(buckets.get(key, [])) < max_examples:
            buckets.setdefault(key, []).append(pid)

    out: list[dict[str, Any]] = []
    for key, cnt in counts.most_common():
        out.append(
            {
                "pattern_key": key,
                "count": cnt,
                "examples": buckets.get(key, []),
            }
        )
    return out


def _snap_dict(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def losing_trade_condition_key(row: dict[str, Any]) -> str:
    """Kompakte Bedingung aus Signal/Features für Verlust-Trades."""
    sig = _snap_dict(row.get("signal_snapshot_json"))
    feat = extract_primary_feature_snapshot(row.get("feature_snapshot_json"))
    market_regime = normalize_market_regime(sig.get("market_regime"))
    if market_regime is None:
        market_regime = normalize_market_regime(row.get("market_regime")) or "unknown"
    parts = [
        f"tf={sig.get('timeframe', '?')}",
        f"class={sig.get('signal_class', '?')}",
        f"regime={market_regime}",
        f"regime_bias={sig.get('regime_bias', '?')}",
        f"multi_tf={sig.get('multi_timeframe_score_0_100', '?')}",
        f"struct={sig.get('structure_score_0_100', '?')}",
        f"atrp={feat.get('atrp_14', '?')}",
        f"exec_cost={_bucket_float(feat.get('execution_cost_bps'), low=5.0, high=12.0)}",
        f"depth={_bucket_float(feat.get('depth_to_bar_volume_ratio'), low=0.4, high=1.0)}",
        f"liq_src={feat.get('liquidity_source', '?')}",
    ]
    return "|".join(str(p) for p in parts)


def top_losing_conditions(rows: list[dict[str, Any]], *, limit: int = 10) -> list[dict[str, Any]]:
    losses = [r for r in rows if _dec_loss(r)]
    cnt: Counter[str] = Counter()
    examples: dict[str, list[str]] = {}
    for r in losses:
        k = losing_trade_condition_key(r)
        cnt[k] += 1
        pid = str(r.get("paper_trade_id", ""))
        if pid and k not in examples:
            examples[k] = []
        if pid and len(examples.get(k, [])) < 3:
            examples.setdefault(k, []).append(pid)
    out = []
    for key, c in cnt.most_common(limit):
        out.append({"condition_key": key, "count": c, "examples": examples.get(key, [])})
    return out


def _dec_loss(row: dict[str, Any]) -> bool:
    from decimal import Decimal

    try:
        pnl = Decimal(str(row.get("pnl_net_usdt", "0")))
    except Exception:
        pnl = Decimal("0")
    return pnl < 0


def label_frequency_on_losses(rows: list[dict[str, Any]], label: str) -> int:
    target = label.strip().upper()
    n = 0
    for r in rows:
        if not _dec_loss(r):
            continue
        labels = _parse_labels(r.get("error_labels_json"))
        if target in labels:
            n += 1
    return n


def _bucket_float(value: Any, *, low: float, high: float) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "missing"
    if numeric < low:
        return "low"
    if numeric > high:
        return "high"
    return "mid"
