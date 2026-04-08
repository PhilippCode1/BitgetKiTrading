"""Online-Drift: Block-Aktionen und Merge (Prompt 26)."""

from __future__ import annotations

from typing import Literal

OnlineDriftAction = Literal["ok", "warn", "shadow_only", "hard_block"]

_ACTION_RANK: dict[str, int] = {
    "ok": 0,
    "warn": 1,
    "shadow_only": 2,
    "hard_block": 3,
}


def normalize_online_drift_action(raw: str | None) -> OnlineDriftAction:
    s = str(raw or "").strip().lower()
    if s in _ACTION_RANK:
        return s  # type: ignore[return-value]
    return "ok"


def merge_online_drift_actions(*actions: str | None) -> OnlineDriftAction:
    best: OnlineDriftAction = "ok"
    best_r = 0
    for a in actions:
        n = normalize_online_drift_action(a)
        r = _ACTION_RANK[n]
        if r > best_r:
            best_r = r
            best = n
    return best


def action_rank(action: str | None) -> int:
    return _ACTION_RANK.get(normalize_online_drift_action(action), 0)
