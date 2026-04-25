#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from shared_py.private_credentials import evaluate_private_credentials, snapshot_to_payload


def parse_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        k, v = stripped.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def build_snapshot(env: dict[str, str], *, dry_run: bool, strict_runtime: bool) -> dict[str, object]:
    # Kein Netzwerkaufruf in diesem Script: Runtime-Modus bleibt read-only/contract-basiert.
    read_only_checked = not strict_runtime or dry_run
    private_auth_ok = None if strict_runtime else True
    permission_trading = None
    permission_withdrawal = None
    revoked_or_expired = False
    rotation_required = False

    snap = evaluate_private_credentials(
        bitget_api_key=env.get("BITGET_API_KEY"),
        bitget_api_secret=env.get("BITGET_API_SECRET"),
        bitget_api_passphrase=env.get("BITGET_API_PASSPHRASE"),
        bitget_demo_enabled=env.get("BITGET_DEMO_ENABLED", "false").lower() == "true",
        execution_mode=env.get("EXECUTION_MODE", "paper"),
        live_trade_enable=env.get("LIVE_TRADE_ENABLE", "false").lower() == "true",
        live_broker_enabled=env.get("LIVE_BROKER_ENABLED", "false").lower() == "true",
        read_only_checked=read_only_checked,
        private_auth_ok=private_auth_ok,
        permission_trading=permission_trading,
        permission_withdrawal=permission_withdrawal,
        revoked_or_expired=revoked_or_expired,
        rotation_required=rotation_required,
        all_live_gates_ok=False,
    )
    payload = snapshot_to_payload(snap)
    payload["mode"] = "dry-run" if dry_run else "strict-runtime"
    payload["network_calls"] = 0
    payload["runtime_readonly_external_step_required"] = bool(strict_runtime)
    return payload


def to_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Private Bitget Credential Check",
        "",
        f"- Modus: `{payload.get('mode')}`",
        f"- Credential-Status: `{payload.get('credential_status')}`",
        f"- Demo-Modus: `{payload.get('demo_modus')}`",
        f"- Read-only geprüft: `{payload.get('read_only_geprueft')}`",
        f"- Trading-Permission erkannt: `{payload.get('trading_permission_erkannt')}`",
        f"- Withdrawal-Permission erkannt: `{payload.get('withdrawal_permission_erkannt')}`",
        f"- Live-Write blockiert: `{payload.get('live_write_blocked')}`",
        f"- Letzte Prüfung: `{payload.get('letzte_pruefung')}`",
        "",
        "## Credential-Hints (redacted)",
    ]
    hints = payload.get("credential_hints", {})
    if isinstance(hints, dict):
        for k in ("api_key", "api_secret", "passphrase"):
            lines.append(f"- {k}: `{hints.get(k)}`")
    lines.append("")
    lines.append("## Blockgründe")
    block = payload.get("blockgruende_de", [])
    if isinstance(block, list) and block:
        for b in block:
            lines.append(f"- {b}")
    else:
        lines.append("- Keine zusätzlichen Blockgründe.")
    if payload.get("runtime_readonly_external_step_required"):
        lines.extend(
            [
                "",
                "## Externer Read-only Schritt",
                "- Runtime-Read-only-Verifikation muss extern gegen Bitget-Private-Read-only-Endpunkt durchgeführt werden.",
                "- Dieses Script sendet niemals Orders.",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Prüft private Bitget-Credential-Sicherheit (Single-Owner).")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--env-file", default=".env.local")
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--strict-runtime", action="store_true")
    parser.add_argument("--output-md")
    args = parser.parse_args()

    env_path = Path(args.env_file)
    env = parse_env_file(env_path)
    payload = build_snapshot(env, dry_run=args.dry_run or args.template, strict_runtime=args.strict_runtime)

    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.output_md:
        out = Path(args.output_md)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(to_markdown(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
