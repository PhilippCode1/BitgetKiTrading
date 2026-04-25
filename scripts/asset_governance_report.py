#!/usr/bin/env python3
"""Erzeugt einen deutschen Asset-Governance-Report aus Fixture-Daten."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from shared_py.bitget.asset_governance import (  # noqa: E402
    AssetGovernanceRecord,
    live_block_reasons,
    now_iso,
)

DEFAULT_INPUT = ROOT / "tests" / "fixtures" / "asset_governance_sample.json"


def _redact_secret_like_values(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, raw in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in ("secret", "token", "password", "key")):
                out[key] = "***REDACTED***"
            else:
                out[key] = _redact_secret_like_values(raw)
        return out
    if isinstance(value, list):
        return [_redact_secret_like_values(item) for item in value]
    return value


def load_records(path: Path) -> list[AssetGovernanceRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload if isinstance(payload, list) else payload.get("assets", [])
    if not isinstance(items, list):
        raise ValueError("input-json muss eine Liste oder {'assets': [...]} enthalten.")
    return [AssetGovernanceRecord.model_validate(item) for item in items]


def build_markdown(records: list[AssetGovernanceRecord]) -> str:
    state_counts = Counter(item.state for item in records)
    with_missing_evidence = [item.symbol for item in records if not item.evidence_refs]
    risk_assets = [
        item.symbol
        for item in records
        if item.state in {"delisted", "suspended"} or not item.bitget_status_clear
    ]
    live_allowed = [
        item.symbol for item in records if item.state == "live_allowed" and not live_block_reasons(item)
    ]
    blocked = [item.symbol for item in records if live_block_reasons(item)]
    quarantine = [item.symbol for item in records if item.state == "quarantine"]
    lines = [
        "# Asset Governance Report",
        "",
        f"- Datum/Zeit: `{now_iso()}`",
        "- Projekt: `bitget-btc-ai`",
        "",
        "## Anzahl Assets je Zustand",
        "",
    ]
    for key, value in sorted(state_counts.items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Live erlaubt",
            "",
            *([f"- `{symbol}`" for symbol in live_allowed] or ["- Keine live_allowed Assets ohne Blocker."]),
            "",
            "## Blockierte Assets",
            "",
            *([f"- `{symbol}`" for symbol in blocked] or ["- Keine blockierten Assets."]),
            "",
            "## Quarantaene-Assets",
            "",
            *([f"- `{symbol}`" for symbol in quarantine] or ["- Keine Assets in Quarantaene."]),
            "",
            "## Assets mit fehlender Evidence",
            "",
            *([f"- `{symbol}`" for symbol in with_missing_evidence] or ["- Keine offenen Evidence-Luecken."]),
            "",
            "## Assets mit Delisting/Suspension-Risiko",
            "",
            *([f"- `{symbol}`" for symbol in risk_assets] or ["- Kein Delisting/Suspension-Risiko sichtbar."]),
            "",
            "## Naechste Freigabeaufgaben fuer Philipp",
            "",
            "- Nur Assets aus `live_candidate` mit vollstaendiger Evidence weiterpruefen.",
            "- Bei fehlender Datenqualitaet/Liquiditaet/Strategy-Evidence Asset blockiert lassen.",
            "- Jede Freigabe mit Actor `Philipp`, Zeitstempel und Grund dokumentieren.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--input-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args(argv)

    if args.dry_run:
        print("asset_governance_report: dry-run=true (fixture/read-only)")
        print("planned_steps=load_records,evaluate_blockers,render_markdown")
        return 0

    input_path = args.input_json or DEFAULT_INPUT
    records = load_records(input_path)
    report = build_markdown(records)
    report = json.loads(json.dumps(_redact_secret_like_values({"md": report})))["md"]

    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(report, encoding="utf-8")

    print(f"asset_governance_report: assets={len(records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
