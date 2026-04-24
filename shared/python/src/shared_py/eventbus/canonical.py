"""
Deterministische Serialisierung fuer Event-Fingerprints und Replay-Vergleiche.

Siehe docs/contracts_determinism.md fuer Stabilitaetsgrad und Grenzen (Wall-Clock,
Floats, UUIDs).
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .envelope import EventEnvelope

_FLOAT_DECIMALS = 8
_UTC = timezone.utc


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


def _is_ms_timestamp_key(k: str) -> bool:
    if not k or not isinstance(k, str):
        return False
    if k in ("exchange_ts_ms", "ingest_ts_ms"):
        return True
    return k.endswith("_ts_ms")


def ms_to_iso_utc_z_micros(ms: int) -> str:
    """Eindeutige UTC-Zeit aus Epoch-Millisekunden (6 Nachkommastellen, Z-Suffix)."""
    if not isinstance(ms, int) or isinstance(ms, bool):
        raise TypeError(ms)
    if ms < 0:
        raise ValueError(ms)
    dt = datetime.fromtimestamp(ms / 1000.0, tz=_UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{dt.microsecond:06d}Z"


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


def canonicalize_json_value(value: Any, *, _key: str | None = None) -> Any:
    """Rekursiv sortierte Keys, 8-Dezimal-Floats, *_ts_ms als ISO-8601-UTC-String (µs, Z)."""
    if _key is not None and _is_ms_timestamp_key(_key) and isinstance(value, int) and not isinstance(
        value, bool
    ):
        return ms_to_iso_utc_z_micros(value)
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
        return {k: canonicalize_json_value(value[k], _key=k) for k in sorted(value.keys())}
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=_UTC)
        else:
            value = value.astimezone(_UTC)
        return value.strftime("%Y-%m-%dT%H:%M:%S") + f".{value.microsecond:06d}Z"
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


def event_envelope_to_canonical_json_text(env: EventEnvelope) -> str:
    """
    Draht-JSON identisch sortiert/gerundet wie Fingerprint-Stack
    (Redis `data` / forensische Byte-Identitaet).
    """
    return stable_json_dumps(env.model_dump(mode="json", exclude_none=False))
