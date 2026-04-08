"""
Einheitliche JSON-Vertraege fuer Learning-Drift (api-gateway + learning-engine).

Vermeidet uneinheitliche Fehlerobjekte und liefert bei fehlender DB-Zeile bzw. leerer
Event-Liste stabile 200er-Payloads. Optional: Metadaten aus config/seeds/.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_ONLINE_LOOKBACK_MINUTES = 60

_SEED_CANDIDATES = (
    "LEARNING_DRIFT_METADATA_SEED_JSON",
    "LEARNING_DRIFT_ONLINE_FALLBACK_JSON",
)


def _repo_root_guess() -> Path:
    """shared_py liegt unter <root>/shared/python/src/shared_py."""
    return Path(__file__).resolve().parents[4]


def load_optional_drift_seed_metadata() -> dict[str, Any] | None:
    """
    Kleiner lokaler Fallback: JSON aus Umgebungspfad oder Standard-Seed-Datei.
    Nur fuer leere Drift-Listen / fehlenden Online-State als Zusatzfeld, keine Fake-Events.
    """
    paths: list[Path] = []
    for env_key in _SEED_CANDIDATES:
        raw = (os.environ.get(env_key) or "").strip()
        if raw:
            paths.append(Path(raw))
    paths.append(_repo_root_guess() / "config" / "seeds" / "drift_metadata_fallback.json")
    paths.append(Path("/app/config/seeds/drift_metadata_fallback.json"))

    seen: set[str] = set()
    for p in paths:
        key = str(p.resolve()) if p.is_absolute() else str(p)
        if key in seen:
            continue
        seen.add(key)
        try:
            if p.is_file():
                data = json.loads(p.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            continue
    return None


def drift_recent_response(*, items: list[dict[str, Any]], limit: int) -> dict[str, Any]:
    out: dict[str, Any] = {
        "status": "ok",
        "items": items,
        "limit": limit,
        "seeded": False,
    }
    if not items:
        meta = load_optional_drift_seed_metadata()
        if meta is not None:
            out["seed_metadata"] = meta
            out["seeded"] = True
    return out


def gateway_online_drift_state_response(row: dict[str, Any] | None) -> dict[str, Any]:
    """
    Gateway: { item, status, seeded?, seed_metadata? } — kompatibel zum Dashboard (item nullable).
    """
    if row is not None:
        return {"status": "ok", "item": row, "seeded": False}
    out: dict[str, Any] = {
        "status": "ok",
        "item": None,
        "detail": None,
        "seeded": False,
    }
    meta = load_optional_drift_seed_metadata()
    if meta is not None:
        out["seed_metadata"] = meta
        out["seeded"] = True
    return out


def learning_engine_online_drift_state_body(row: dict[str, Any] | None) -> dict[str, Any]:
    """
    learning-engine: flache Felder wie bisher, aber 200 statt 503 bei fehlender Zeile.
    """
    if row is not None:
        return {
            "status": "ok",
            "seeded": False,
            "scope": row["scope"],
            "effective_action": row["effective_action"],
            "computed_at": row["computed_at"].isoformat() if row.get("computed_at") else None,
            "lookback_minutes": row["lookback_minutes"],
            "breakdown_json": row.get("breakdown_json") or {},
        }
    body: dict[str, Any] = {
        "status": "ok",
        "seeded": False,
        "scope": "global",
        "effective_action": "ok",
        "computed_at": None,
        "lookback_minutes": DEFAULT_ONLINE_LOOKBACK_MINUTES,
        "breakdown_json": {
            "_meta": {
                "empty": True,
                "note_de": "Kein Eintrag in learn.online_drift_state (Migration/evaluate-now ausstehend).",
            }
        },
    }
    meta = load_optional_drift_seed_metadata()
    if meta is not None:
        body["seed_metadata"] = meta
        body["seeded"] = True
    return body
