"""
Deterministische Serialisierung fuer Event-Fingerprints und Replay-Vergleiche.

Siehe docs/contracts_determinism.md fuer Stabilitaetsgrad und Grenzen (Wall-Clock,
Floats, UUIDs).
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Literal

from .envelope import EventEnvelope

_FLOAT_DECIMALS = 8


def _load_event_streams_catalog() -> dict[str, Any]:
    for base in Path(__file__).resolve().parents:
        path = base / "shared" / "contracts" / "catalog" / "event_streams.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError(
        "shared/contracts/catalog/event_streams.json nicht gefunden "
        "(Monorepo-Root erwartet)."
    )


_CAT = _load_event_streams_catalog()
_fp_ver = _CAT["envelope_fingerprint_canon_version"]
ENVELOPE_FINGERPRINT_CANON_VERSION: str = str(_fp_ver)

# Semantik: fachlicher Kern ohne transportgebundene IDs und ohne Wall-Clock.
_SEMANTIC_FIELD_NAMES: tuple[str, ...] = (
    "schema_version",
    "event_type",
    "symbol",
    "instrument",
    "timeframe",
    "exchange_ts_ms",
    "dedupe_key",
    "payload",
    "trace",
)

# Wire: vollstaendige persistierbare Huellle inkl. event_id und ingest_ts_ms.
_WIRE_FIELD_NAMES: tuple[str, ...] = (
    "schema_version",
    "event_id",
    "event_type",
    "symbol",
    "instrument",
    "timeframe",
    "exchange_ts_ms",
    "ingest_ts_ms",
    "dedupe_key",
    "payload",
    "trace",
)

FingerprintMode = Literal["semantic", "wire"]


def normalize_json_number(value: float) -> float | int:
    """Gleicht JSON-Zahlen fuer Cross-Runtime-Fingerprints an (explizite FP-Policy)."""
    if not isinstance(value, float):
        raise TypeError(value)
    if math.isnan(value) or math.isinf(value):
        raise ValueError("NaN/Inf in fingerprint material nicht erlaubt")
    rounded = round(value, _FLOAT_DECIMALS)
    as_int = int(rounded)
    eps = 10 ** (-(_FLOAT_DECIMALS + 1))
    if math.isclose(rounded, float(as_int), rel_tol=0.0, abs_tol=eps):
        return as_int
    return rounded


def canonicalize_json_value(value: Any) -> Any:
    """Rekursiv sortierte Keys, normalisierte Floats, stabile Listen."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return normalize_json_number(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [canonicalize_json_value(v) for v in value]
    if isinstance(value, dict):
        return {k: canonicalize_json_value(value[k]) for k in sorted(value.keys())}
    raise TypeError(f"nicht unterstuetzter Typ fuer Kanonisierung: {type(value)!r}")


def stable_json_dumps(obj: Any) -> str:
    """Kompaktes JSON, UTF-8, sortierte Objektschluessel auf allen Ebenen."""
    return json.dumps(
        canonicalize_json_value(obj),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _envelope_field_subset(
    data: dict[str, Any],
    fields: tuple[str, ...],
) -> dict[str, Any]:
    return {k: data[k] for k in fields if k in data}


def envelope_fingerprint_preimage(
    env: EventEnvelope | dict[str, Any],
    *,
    mode: FingerprintMode,
) -> dict[str, Any]:
    """
    Baut das Hash-Material (vor SHA-256) inkl. canon_version-Wrapper.

    mode=semantic: ohne event_id und ingest_ts_ms (Dedupe / Replay-Gleichheit).
    mode=wire: alle persistierten Huellenfelder.
    """
    if isinstance(env, EventEnvelope):
        data = env.model_dump(mode="json", exclude_none=False)
    else:
        data = dict(env)
    if mode == "semantic":
        material = _envelope_field_subset(data, _SEMANTIC_FIELD_NAMES)
    else:
        material = _envelope_field_subset(data, _WIRE_FIELD_NAMES)
    return {
        "canon_version": ENVELOPE_FINGERPRINT_CANON_VERSION,
        "fingerprint_mode": mode,
        "envelope": material,
    }


def envelope_fingerprint_sha256(
    env: EventEnvelope | dict[str, Any],
    *,
    mode: FingerprintMode,
) -> str:
    preimage = envelope_fingerprint_preimage(env, mode=mode)
    body = stable_json_dumps(preimage)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
