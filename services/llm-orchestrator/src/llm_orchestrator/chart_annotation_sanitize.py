"""Nachbearbeitung von chart_annotations (strategy_signal_explain).

Ziel: typische Modellfehler (Unix ms statt s) korrigieren und Array-Laengen begrenzen,
ohne Schema-Validierung zu ersetzen — die UI sanitziert weiterhin gegen Kerzen-Stats.
"""

from __future__ import annotations

import copy
import math
from typing import Any

_MS_THRESHOLD = 10**11

_MAX_LEN = {
    "horizontal_lines": 12,
    "price_bands": 8,
    "time_markers": 24,
    "line_segments": 16,
    "vertical_rules": 12,
    "uncertainty_regions": 8,
    "chart_notes_de": 8,
}


def _coerce_unix_s(val: Any) -> tuple[int | None, bool]:
    if isinstance(val, bool):
        return None, False
    if isinstance(val, int):
        n = val
    elif isinstance(val, float) and val == int(val):
        n = int(val)
    elif isinstance(val, float) and math.isfinite(val):
        n = int(val)
    else:
        return None, False
    corrected = False
    if n > _MS_THRESHOLD:
        n = int(n / 1000)
        corrected = True
    return n, corrected


def sanitize_strategy_chart_annotations(ca: Any) -> tuple[Any, int]:
    """
    Gibt (payload, ms_korrekturen_anzahl) zurueck.
    Bei ungueltigem Top-Level wird (None, 0) geliefert — chart_annotations entfernen.
    """
    if ca is None:
        return None, 0
    if not isinstance(ca, dict):
        return None, 0
    if ca.get("schema_version") != "1.0":
        return None, 0

    out = copy.deepcopy(ca)
    fixes = 0

    markers = out.get("time_markers")
    if isinstance(markers, list):
        out["time_markers"] = markers[: _MAX_LEN["time_markers"]]
        for row in out["time_markers"]:
            if not isinstance(row, dict):
                continue
            if "time_unix_s" in row:
                s, c = _coerce_unix_s(row["time_unix_s"])
                if s is not None:
                    row["time_unix_s"] = s
                    if c:
                        fixes += 1

    segs = out.get("line_segments")
    if isinstance(segs, list):
        out["line_segments"] = segs[: _MAX_LEN["line_segments"]]
        for row in out["line_segments"]:
            if not isinstance(row, dict):
                continue
            for k in ("time_a_unix_s", "time_b_unix_s"):
                if k in row:
                    s, c = _coerce_unix_s(row[k])
                    if s is not None:
                        row[k] = s
                        if c:
                            fixes += 1

    vr = out.get("vertical_rules")
    if isinstance(vr, list):
        out["vertical_rules"] = vr[: _MAX_LEN["vertical_rules"]]
        for row in out["vertical_rules"]:
            if not isinstance(row, dict):
                continue
            if "time_unix_s" in row:
                s, c = _coerce_unix_s(row["time_unix_s"])
                if s is not None:
                    row["time_unix_s"] = s
                    if c:
                        fixes += 1

    ur = out.get("uncertainty_regions")
    if isinstance(ur, list):
        out["uncertainty_regions"] = ur[: _MAX_LEN["uncertainty_regions"]]
        for row in out["uncertainty_regions"]:
            if not isinstance(row, dict):
                continue
            for k in ("time_from_unix_s", "time_to_unix_s"):
                if k in row:
                    s, c = _coerce_unix_s(row[k])
                    if s is not None:
                        row[k] = s
                        if c:
                            fixes += 1

    hl = out.get("horizontal_lines")
    if isinstance(hl, list):
        out["horizontal_lines"] = hl[: _MAX_LEN["horizontal_lines"]]

    pb = out.get("price_bands")
    if isinstance(pb, list):
        out["price_bands"] = pb[: _MAX_LEN["price_bands"]]

    notes = out.get("chart_notes_de")
    if isinstance(notes, list):
        out["chart_notes_de"] = notes[: _MAX_LEN["chart_notes_de"]]

    return out, fixes
