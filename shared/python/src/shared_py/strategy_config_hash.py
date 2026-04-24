from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

_JSON_SEP = (",", ":")


def _json_object(
    v: Any,
) -> dict[str, Any]:
    if v is None:
        return {}
    if isinstance(v, dict):
        return v
    if isinstance(v, Mapping):
        return dict(v)
    raise TypeError("strategy config fragment must be a JSON object")


def canonical_config_payload(
    definition: Any,
    parameters: Any,
    risk_profile: Any,
) -> dict[str, Any]:
    return {
        "definition": _json_object(definition),
        "parameters": _json_object(parameters),
        "risk_profile": _json_object(risk_profile),
    }


def compute_configuration_hash(
    definition: Any,
    parameters: Any,
    risk_profile: Any,
) -> str:
    body = canonical_config_payload(definition, parameters, risk_profile)
    raw = json.dumps(
        body,
        sort_keys=True,
        ensure_ascii=False,
        separators=_JSON_SEP,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
