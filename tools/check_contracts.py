#!/usr/bin/env python3
"""
Prueft Contract-Artefakte ohne shared_py-Import (bitget/__init__ zieht config).

Validiert: Envelope-Fixture gegen Schema; Katalog vs. Schema const;
Katalog fingerprint_canon vs. contractVersions.ts;
Katalog streams + live_sse vs. shared/ts/src/eventStreams.ts;
event_envelope.schema.json event_type.enum vs. Katalog;
OpenAPI-JSON (Gateway) Struktur 3.x.

Aus Repo-Root:
  python tools/check_contracts.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


def _parse_ts_event_type_to_stream(ts_text: str) -> dict[str, str]:
    m = re.search(
        r"export const EVENT_TYPE_TO_STREAM = \{([^}]+)\}\s+as\s+const",
        ts_text,
        re.DOTALL,
    )
    if not m:
        raise ValueError("EVENT_TYPE_TO_STREAM-Block in eventStreams.ts nicht gefunden")
    out: dict[str, str] = {}
    for raw in m.group(1).splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        mm = re.match(r"(\w+):\s*\"(events:[^\"]+)\"\s*,?\s*$", line)
        if mm:
            out[mm.group(1)] = mm.group(2)
    return out


def _parse_ts_live_sse_streams(ts_text: str) -> list[str]:
    m = re.search(
        r"export const LIVE_SSE_STREAMS = \[(.*?)\]\s+as\s+const",
        ts_text,
        re.DOTALL,
    )
    if not m:
        raise ValueError("LIVE_SSE_STREAMS-Block in eventStreams.ts nicht gefunden")
    out: list[str] = []
    for raw in m.group(1).splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        mm = re.search(r"\"(events:[^\"]+)\"", line)
        if mm:
            out.append(mm.group(1))
    return out


def _check_ts_catalog_parity(
    *,
    catalog: dict[str, Any],
    ts_path: Path,
) -> list[str]:
    errs: list[str] = []
    ts_text = ts_path.read_text(encoding="utf-8")
    try:
        ts_map = _parse_ts_event_type_to_stream(ts_text)
    except ValueError as e:
        return [str(e)]
    cat_map = {str(row["event_type"]): str(row["stream"]) for row in catalog["streams"]}
    if ts_map != cat_map:
        only_ts = set(ts_map.keys()) - set(cat_map.keys())
        only_cat = set(cat_map.keys()) - set(ts_map.keys())
        mismatch = {k for k in cat_map if k in ts_map and ts_map[k] != cat_map[k]}
        if only_ts:
            errs.append(
                f"eventStreams.ts nur in TS (fehlt im Katalog): {sorted(only_ts)}"
            )
        if only_cat:
            errs.append(f"Katalog nur in JSON (fehlt in TS): {sorted(only_cat)}")
        if mismatch:
            errs.append(f"Stream-Zuordnung abweichend: {sorted(mismatch)}")
    live_cat = [str(s) for s in catalog["live_sse_streams"]]
    try:
        live_ts = _parse_ts_live_sse_streams(ts_text)
    except ValueError as e:
        errs.append(str(e))
        return errs
    if live_ts != live_cat:
        errs.append(
            "live_sse_streams: Katalog != eventStreams.ts LIVE_SSE_STREAMS "
            f"(json={live_cat!r} ts={live_ts!r})"
        )
    return errs


def _check_schema_event_types(
    *,
    catalog: dict[str, Any],
    schema: dict[str, Any],
) -> list[str]:
    enum_raw = schema.get("properties", {}).get("event_type", {}).get("enum")
    if not isinstance(enum_raw, list):
        return ["event_envelope.schema.json: properties.event_type.enum fehlt"]
    enum_set = {str(x) for x in enum_raw}
    cat_set = {str(row["event_type"]) for row in catalog["streams"]}
    if enum_set != cat_set:
        return [
            f"Schema event_type.enum != Katalog streams: "
            f"nur_schema={sorted(enum_set - cat_set)} "
            f"nur_katalog={sorted(cat_set - enum_set)}"
        ]
    return []


def _check_openapi_structure(openapi: dict[str, Any], *, path_label: str) -> list[str]:
    errs: list[str] = []
    ver = openapi.get("openapi")
    if not isinstance(ver, str):
        errs.append(f"{path_label}: fehlt top-level 'openapi' (string)")
    elif not ver.startswith("3."):
        errs.append(f"{path_label}: erwartet OpenAPI 3.x, ist {ver!r}")
    if not isinstance(openapi.get("info"), dict):
        errs.append(f"{path_label}: fehlt 'info' object")
    paths = openapi.get("paths")
    if not isinstance(paths, dict) or not paths:
        errs.append(f"{path_label}: 'paths' muss nicht-leeres object sein")
    return errs


def main() -> int:
    root = Path(__file__).resolve().parents[1]

    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print("jsonschema fehlt", file=sys.stderr)
        return 2

    catalog_path = root / "shared" / "contracts" / "catalog" / "event_streams.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    schema_path = (
        root / "shared" / "contracts" / "schemas" / "event_envelope.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema_ver = schema["properties"]["schema_version"].get("const")
    if schema_ver != catalog["envelope_default_schema_version"]:
        print(
            "event_envelope.schema.json schema_version const != Katalog",
            schema_ver,
            catalog["envelope_default_schema_version"],
            file=sys.stderr,
        )
        return 1

    ts_path = root / "shared" / "ts" / "src" / "contractVersions.ts"
    ts_ver = ts_path.read_text(encoding="utf-8")
    fp_m = re.search(
        r'ENVELOPE_FINGERPRINT_CANON_VERSION\s*=\s*"([^"]+)"\s+as\s+const',
        ts_ver,
    )
    if not fp_m:
        print(
            "ENVELOPE_FINGERPRINT_CANON_VERSION in contractVersions.ts nicht parsebar",
            file=sys.stderr,
        )
        return 1
    if fp_m.group(1) != str(catalog["envelope_fingerprint_canon_version"]):
        print(
            "contractVersions ENVELOPE_FINGERPRINT_CANON_VERSION != Katalog",
            file=sys.stderr,
        )
        return 1
    sch_m = re.search(r'ENVELOPE_SCHEMA_VERSION\s*=\s*"([^"]+)"\s+as\s+const', ts_ver)
    if not sch_m or sch_m.group(1) != catalog["envelope_default_schema_version"]:
        print("contractVersions ENVELOPE_SCHEMA_VERSION != Katalog", file=sys.stderr)
        return 1

    ts_streams_path = root / "shared" / "ts" / "src" / "eventStreams.ts"
    parity_errs = _check_ts_catalog_parity(catalog=catalog, ts_path=ts_streams_path)
    parity_errs.extend(_check_schema_event_types(catalog=catalog, schema=schema))
    if parity_errs:
        print("check_contracts: Katalog/TS/Schema-Paritaet FAILED", file=sys.stderr)
        for line in parity_errs:
            print(f"  {line}", file=sys.stderr)
        return 1

    openapi_path = (
        root / "shared" / "contracts" / "openapi" / "api-gateway.openapi.json"
    )
    openapi = json.loads(openapi_path.read_text(encoding="utf-8"))
    oerr = _check_openapi_structure(openapi, path_label=str(openapi_path.name))
    if oerr:
        print("check_contracts: OpenAPI-Struktur FAILED", file=sys.stderr)
        for line in oerr:
            print(f"  {line}", file=sys.stderr)
        return 1

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    fixture = (
        root / "tests" / "fixtures" / "contracts" / "envelope_candle_close_ok.json"
    )
    instance = json.loads(fixture.read_text(encoding="utf-8"))
    errs = list(validator.iter_errors(instance))
    if errs:
        for e in errs:
            print(f"{list(e.path)}: {e.message}", file=sys.stderr)
        return 1

    print("check_contracts: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
