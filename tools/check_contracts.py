#!/usr/bin/env python3
"""
Prueft Contract-Artefakte ohne shared_py-Import (bitget/__init__ zieht config).

Validiert: Envelope-Fixture gegen Schema; Katalog vs. Schema const;
Katalog fingerprint_canon vs. contractVersions.ts;
Katalog streams + live_sse vs. shared/ts/src/eventStreams.ts;
event_envelope (allOf) event_type.enum vs. Katalog; payload_schema_map.json
vs. jede Datei; JSON-Schema payload vs. shared/ts/src/payloadTypes.ts
(struktur-/Typ-Paritaet, locker fuer generische { [k: string]: unknown });
OpenAPI-JSON (Gateway) Struktur 3.x.

Aus Repo-Root:
  python tools/check_contracts.py
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


def _envelope_object_schema(s: dict[str, Any]) -> dict[str, Any]:
    a = s.get("allOf")
    if isinstance(a, list) and a and a[0].get("type") == "object":
        return a[0]
    if s.get("type") == "object" and s.get("properties") is not None:
        return s
    return s


def _build_contracts_registry(
    root: Path,
) -> tuple[object, object]:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012

    schemas = root / "shared" / "contracts" / "schemas"
    reg: Registry = Registry()  # type: ignore[assignment]
    for f in sorted(schemas.glob("*.schema.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        key = str(doc.get("$id", f"https://bitget-btc-ai.local/schemas/{f.name}"))
        reg = reg.with_resource(  # type: ignore[union-attr]
            key,
            Resource.from_contents(doc, default_specification=DRAFT202012),
        )
    env = json.loads(
        (schemas / "event_envelope.schema.json").read_text(encoding="utf-8")
    )
    v = Draft202012Validator(env, registry=reg)
    Draft202012Validator.check_schema(v.schema)
    return v, reg


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


def _file_to_ts_payload_type(filename: str) -> str:
    b = filename.removeprefix("payload_").removesuffix(".schema.json")
    return "".join(p.title() for p in b.split("_")) + "Payload"


def _ts_type_block_by_name(ts_text: str, type_name: str) -> str:
    m = re.search(
        r"export type " + re.escape(type_name) + r"\s*=\s*\{",
        ts_text,
    )
    if not m:
        return ""
    start = m.end() - 1
    depth = 0
    for j in range(start, len(ts_text)):
        c = ts_text[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return ts_text[start : j + 1]
    return ""


def _ts_fields_from_block(block: str) -> dict[str, str]:
    """key -> Typstring (grob, alles hinter Doppelpunkt, vor Semikolon/NL)."""
    out: dict[str, str] = {}
    for raw in re.split(r"[;\n]", block[1:-1] if block.startswith("{") else block):
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        m = re.match(
            r"^(\w+)(\?)?:\s*(.+?)(?:,)?\s*$",
            line,
        )
        if m:
            out[m.group(1)] = m.group(3).strip()
    return out


def _json_type_tags(prop: object) -> list[str]:
    if not isinstance(prop, dict):
        return ["any"]
    t = prop.get("type")
    if isinstance(t, str):
        return [t]
    if isinstance(t, list):
        return [str(x) for x in t if isinstance(x, str)]
    if "allOf" in prop or "anyOf" in prop or "oneOf" in prop:
        return ["complex"]
    return ["any"]


def _ts_ok_for_json_type(ts_type: str, jtags: list[str]) -> bool:
    """Grob-Validierung: JSON-Schema typ vs. TS-Feld-String (kein tiefes Nesting)."""
    ts_l = re.sub(r"\s+", " ", ts_type).strip()
    if "unknown" in ts_l or re.search(
        r"\[k: string\]\s*:\s*unknown",
        ts_l,
    ):
        return True
    jset = {str(x) for x in jtags if isinstance(x, str) and str(x) != "any"}
    if "array" in jset and re.search(
        r"string\[\]|\]:\s*string|Array<",
        ts_l,
    ):
        return True
    if "null" in jset and "| null" in ts_l:
        base = ts_l.replace(" | null", "").strip()
        for jt in jset - {"null"}:
            if jt in ("integer", "number") and re.search(
                r"number", base, re.IGNORECASE
            ):
                return True
    for jt in jset - {"any"}:
        if jt in ("integer", "number") and re.search(r"number", ts_l, re.IGNORECASE):
            return True
        if jt == "string" and re.search(r"string", ts_l, re.IGNORECASE):
            return True
        if jt == "boolean" and re.search(r"boolean", ts_l, re.IGNORECASE):
            return True
    return False


def _check_ts_schema_payloads(
    *,
    root: Path,
    payload_map: dict[str, str],
) -> list[str]:
    err: list[str] = []
    pay_ts = (root / "shared" / "ts" / "src" / "payloadTypes.ts").read_text(
        encoding="utf-8"
    )
    seen: set[str] = set()
    for _ev, rel in sorted(payload_map.items(), key=lambda x: x[0]):
        if rel in seen:
            continue
        seen.add(rel)
        s_path = root / "shared" / "contracts" / "schemas" / rel
        if not s_path.is_file():
            err.append(f"payload_schema_map: {rel!r} fehlt im schemas-Verzeichnis")
            continue
        sdoc: dict = json.loads(s_path.read_text(encoding="utf-8"))
        tname = _file_to_ts_payload_type(rel)
        if not re.search(
            r"export type " + re.escape(tname) + r"\b",
            pay_ts,
        ):
            err.append(f"payloadTypes.ts: fehlt export type {tname!r} fuer {rel}")
            continue
        block = _ts_type_block_by_name(pay_ts, tname)
        if not block:
            err.append(f"payloadTypes.ts: Block fuer {tname!r} nicht auffindbar")
            continue
        nprops: dict = sdoc.get("properties", {})
        sreq: list = sdoc.get("required", [])
        is_loose = (
            sdoc.get("type") == "object"
            and bool(sdoc.get("additionalProperties", False) is True)
            and (not sdoc.get("required"))
            and (not sdoc.get("properties"))
        )
        if is_loose:
            inner = block.replace("\n", " ")
            if not re.search(r"\[k: string\]\s*:\s*unknown", inner):
                err.append(
                    f"Payload {tname!r} ({rel}): generisches JSON-Schema erwartet"
                    f" `{{ [k: string]: unknown }}` in TS, ist: {block[:200]!r}..."
                )
            continue
        tfields = _ts_fields_from_block(block)
        for rk in sreq:
            rks = str(rk)
            if rks not in tfields and rks in nprops:
                err.append(
                    f"Payload {tname} / {rel}: required JSON {rks!r} in TS fehlt "
                    "(Name abweichend?)"
                )
        for pk, psc in nprops.items():
            if pk not in tfields and pk not in sreq:
                continue
            if pk in tfields:
                jt = _json_type_tags(psc)
                if not _ts_ok_for_json_type(tfields[pk], jt) and not re.search(
                    r"unknown",
                    tfields[pk],
                ):
                    err.append(
                        f"Payload {tname}: Feld {pk!r} jsonschema types={jt!r} "
                        f"-> TS {tfields[pk]!r} (Grob-Check) "
                        f"({rel})"
                    )
    return err


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

    if importlib.util.find_spec("jsonschema") is None:
        print("jsonschema fehlt", file=sys.stderr)
        return 2

    catalog_path = root / "shared" / "contracts" / "catalog" / "event_streams.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    schema_path = (
        root / "shared" / "contracts" / "schemas" / "event_envelope.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    base = _envelope_object_schema(schema)
    schema_prop = (base or {}).get("properties") or {}
    schema_ver = (schema_prop.get("schema_version") or {}).get("const")
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
    payload_map: dict[str, str] = json.loads(
        (
            root / "shared" / "contracts" / "catalog" / "payload_schema_map.json"
        ).read_text(encoding="utf-8")
    )
    cat_ev = {str(r["event_type"]) for r in catalog["streams"]}
    if set(payload_map.keys()) != cat_ev:
        print(
            "check_contracts: payload_schema_map.json != Katalog event_types",
            set(payload_map.keys()) ^ cat_ev,
            file=sys.stderr,
        )
        return 1

    parity_errs = _check_ts_catalog_parity(catalog=catalog, ts_path=ts_streams_path)
    parity_errs.extend(_check_schema_event_types(catalog=catalog, schema=base or {}))
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

    ts_pl_errs = _check_ts_schema_payloads(root=root, payload_map=payload_map)
    if ts_pl_errs:
        print(
            "check_contracts: TS/JSON-Schema-Payload-Paritaet FAILED",
            file=sys.stderr,
        )
        for line in ts_pl_errs:
            print(f"  {line}", file=sys.stderr)
        return 1

    validator, _ = _build_contracts_registry(root)

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
