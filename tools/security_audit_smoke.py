#!/usr/bin/env python3
"""
Optionale End-to-End-Checks gegen ein laufendes API-Gateway (HTTP).

Ohne erreichbare base-url: klarer Non-PASS-Exit (kein fiktives „alles grün“).
Mit --strict: jeder Check muss bestanden werden, sonst Exit 2.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, UTC
from typing import Any


def _get(url: str, timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def _try_json(b: bytes) -> Any:
    try:
        return json.loads(b.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None


def run_checks(base: str, timeout: float) -> list[tuple[str, bool, str]]:
    b = base.rstrip("/")
    out: list[tuple[str, bool, str]] = []
    # Öffentliche Readiness
    for path, name in (
        ("/health", "GET /health"),
        ("/ready", "GET /ready"),
    ):
        try:
            code, _ = _get(b + path, timeout)
            ok = code in (200, 204)
            out.append((name, ok, f"status={code}"))
        except Exception as e:
            out.append((name, False, str(e)))
    # Sensible/Operator-Routen ohne Auth
    for path, label in (
        ("/v1/system/health", "GET /v1/system/health unauthenticated"),
        ("/v1/commerce/customer/me", "GET /v1/commerce/customer/me unauthenticated"),
        ("/v1/admin/llm-governance", "GET /v1/admin/llm-governance unauthenticated"),
    ):
        try:
            code, body = _get(f"{b}{path}", timeout)
            ok = code in (401, 403)
            detail = f"status={code}"
            if not ok and body:
                detail += " body=" + body[:120].decode("utf-8", errors="replace")
            out.append((label, ok, detail))
        except Exception as e:
            out.append((label, False, str(e)))
    return out


def _md(
    base: str,
    results: list[tuple[str, bool, str]],
    *,
    block_reason: str | None,
) -> str:
    ts = datetime.now(UTC).isoformat()
    h = f"# security_audit_smoke\n\n**Base:** `{base}`  \n**Zeit:** `{ts}`  \n**Block:** {block_reason or 'none'}\n\n| Check | OK | Detail |\n| --- | --- | --- |\n"
    for name, ok, d in results:
        h += f"| {name} | {'ja' if ok else 'nein'} | {d} |\n"
    return h


def main() -> int:
    p = argparse.ArgumentParser(
        description="Sicherheits-Smoke für API-Gateway (optional, laufendes Ziel nötig)."
    )
    p.add_argument(
        "--base-url",
        default="",
        help="z. B. http://127.0.0.1:8000 (leer = nur Blocked-Report)",
    )
    p.add_argument(
        "--timeout-sec",
        type=float,
        default=5.0,
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Jeder Check muss ok sein.",
    )
    p.add_argument(
        "--report-md",
        type=str,
        default="",
        metavar="PATH",
        help="Markdown schreiben.",
    )
    args = p.parse_args()
    base = (args.base_url or "").strip()
    if not base:
        msg = "BLOCKED_EXTERNAL: kein --base-url (laufendes API-Gateway erforderlich) — kein automatisierter E2E-Security-PASS im Klon."
        print(msg, file=sys.stderr)
        if args.report_md:
            open(args.report_md, "w", encoding="utf-8").write(
                _md(
                    "<none>",
                    [],
                    block_reason="no_base_url",
                )
                + f"\n\n> {msg}\n"
            )
        return 3
    block: str | None = None
    try:
        _get(base + "/health", min(args.timeout_sec, 2.0))
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        block = f"verbindung: {e}"
        print("BLOCKED_EXTERNAL: Ziel nicht erreichbar —", e, file=sys.stderr)
        if args.report_md:
            open(args.report_md, "w", encoding="utf-8").write(
                _md(base, [], block_reason=block) + "\n"
            )
        return 3

    results = run_checks(base, args.timeout_sec)
    for name, ok, d in results:
        print(f"{'OK' if ok else 'FAIL'}: {name} — {d}")
    if args.report_md:
        open(args.report_md, "w", encoding="utf-8").write(
            _md(base, results, block_reason=None) + "\n"
        )
    if args.strict and not all(ok for _, ok, __ in results):
        print("STRICT: mindestens ein Check fehlgeschlagen", file=sys.stderr)
        return 2
    if not all(ok for _, ok, __ in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
