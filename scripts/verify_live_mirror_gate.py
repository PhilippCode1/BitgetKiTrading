#!/usr/bin/env python3
"""
Verifier fuer Prompt 09: Live-Mirror-Gate.

- Liest eine ENV-Datei.
- Prueft Pflicht-Gates fuer Live-Opening.
- Gibt bei --dry-run einen maschinenlesbaren Report aus.
- Fail-Closed fuer Fake-/Demo-/Localhost-Marker in Production-Profilen.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TRUTHY = {"1", "true", "yes", "on"}
FALSY = {"0", "false", "no", "off"}
_BAD_VALUE_RE = re.compile(
    r"(fake|fixture|mock|demo|sandbox|example\.com|localhost|127\.0\.0\.1|0\.0\.0\.0)",
    re.IGNORECASE,
)
_PROVIDER_BAD_RE = re.compile(r"(provider.*(fake|demo)|fake.*provider)", re.IGNORECASE)


@dataclass(frozen=True)
class GateCheck:
    key: str
    expected: str
    actual: str
    ok: bool
    reason: str


def _parse_env_file(env_file: Path) -> dict[str, str]:
    if not env_file.exists():
        raise FileNotFoundError(f"env file nicht gefunden: {env_file}")
    values: dict[str, str] = {}
    for raw_line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        if "#" in value:
            value = value.split("#", 1)[0].strip()
        values[key] = value.strip()
    return values


def _norm_bool(value: str | None) -> str:
    if value is None:
        return ""
    n = value.strip().lower()
    if n in TRUTHY:
        return "true"
    if n in FALSY:
        return "false"
    return n


def _check_equals(env: dict[str, str], key: str, expected: str) -> GateCheck:
    actual = (env.get(key) or "").strip()
    ok = actual.lower() == expected.lower()
    reason = "ok" if ok else f"{key} erwartet {expected!r}, ist {actual!r}"
    return GateCheck(key=key, expected=expected, actual=actual, ok=ok, reason=reason)


def _check_bool(env: dict[str, str], key: str, expected: bool) -> GateCheck:
    expected_txt = "true" if expected else "false"
    actual_raw = env.get(key)
    actual = _norm_bool(actual_raw)
    ok = actual == expected_txt
    reason = "ok" if ok else f"{key} erwartet {expected_txt!r}, ist {actual_raw!r}"
    return GateCheck(key=key, expected=expected_txt, actual=actual_raw or "", ok=ok, reason=reason)


def _check_leverage_caps(env: dict[str, str]) -> list[GateCheck]:
    out: list[GateCheck] = []
    allowed_raw = (env.get("RISK_ALLOWED_LEVERAGE_MAX") or "").strip()
    ramp_raw = (env.get("RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE") or "").strip()
    try:
        allowed = int(allowed_raw)
        ramp = int(ramp_raw)
    except ValueError:
        out.append(
            GateCheck(
                key="RISK_ALLOWED_LEVERAGE_MAX",
                expected="int<=7",
                actual=allowed_raw,
                ok=False,
                reason="RISK_ALLOWED_LEVERAGE_MAX muss int sein",
            )
        )
        out.append(
            GateCheck(
                key="RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE",
                expected="int<=7",
                actual=ramp_raw,
                ok=False,
                reason="RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE muss int sein",
            )
        )
        return out

    out.append(
        GateCheck(
            key="RISK_ALLOWED_LEVERAGE_MAX",
            expected="<=7",
            actual=allowed_raw,
            ok=allowed <= 7,
            reason="ok" if allowed <= 7 else "Startprofil verletzt: RISK_ALLOWED_LEVERAGE_MAX > 7",
        )
    )
    out.append(
        GateCheck(
            key="RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE",
            expected="<=7 and <=RISK_ALLOWED_LEVERAGE_MAX",
            actual=ramp_raw,
            ok=(ramp <= 7 and ramp <= allowed),
            reason=(
                "ok"
                if (ramp <= 7 and ramp <= allowed)
                else "Startprofil verletzt: Ramp-Cap > 7 oder > RISK_ALLOWED_LEVERAGE_MAX"
            ),
        )
    )
    return out


def _detect_production_smells(env: dict[str, str]) -> list[str]:
    findings: list[str] = []
    for key, raw in env.items():
        value = (raw or "").strip()
        if not value:
            continue
        lower = value.lower()
        if _BAD_VALUE_RE.search(lower):
            findings.append(f"{key} enthaelt verbotenen Marker: {value!r}")
        if _PROVIDER_BAD_RE.search(lower):
            findings.append(f"{key} enthaelt Fake-Provider-Hinweis: {value!r}")
    return findings


def evaluate(env: dict[str, str]) -> dict[str, Any]:
    checks: list[GateCheck] = []
    checks.extend(
        [
            _check_bool(env, "PRODUCTION", True),
            _check_equals(env, "APP_ENV", "production"),
            _check_equals(env, "EXECUTION_MODE", "live"),
            _check_bool(env, "LIVE_TRADE_ENABLE", True),
            _check_bool(env, "LIVE_BROKER_ENABLED", True),
            _check_bool(env, "LIVE_REQUIRE_EXECUTION_BINDING", True),
            _check_bool(env, "LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN", True),
            _check_bool(env, "REQUIRE_SHADOW_MATCH_BEFORE_LIVE", True),
            _check_bool(env, "LIVE_KILL_SWITCH_ENABLED", True),
            _check_bool(env, "RISK_HARD_GATING_ENABLED", True),
            _check_bool(env, "RISK_REQUIRE_7X_APPROVAL", True),
            _check_equals(env, "RISK_ALLOWED_LEVERAGE_MIN", "7"),
            _check_bool(env, "BITGET_DEMO_ENABLED", False),
            _check_bool(env, "NEWS_FIXTURE_MODE", False),
            _check_bool(env, "LLM_USE_FAKE_PROVIDER", False),
            _check_bool(env, "PAPER_SIM_MODE", False),
        ]
    )
    checks.extend(_check_leverage_caps(env))

    not_ready = [c.reason for c in checks if not c.ok]
    prod_smells = _detect_production_smells(env)
    prod_smells = [s for s in prod_smells if "APP_ENV" not in s]

    verdict = "PASS"
    if prod_smells:
        verdict = "FAIL"
    elif not_ready:
        verdict = "NOT_READY"
    return {
        "verdict": verdict,
        "gate_checks": [c.__dict__ for c in checks],
        "not_ready_reasons": not_ready,
        "production_smells": prod_smells,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Live-Mirror-Gate readiness.")
    parser.add_argument(
        "--env-file",
        default=".env.production.example",
        help="Pfad zur ENV-Datei (Default: .env.production.example)",
    )
    parser.add_argument("--strict", action="store_true", help="Exit != 0 bei NOT_READY/FAIL")
    parser.add_argument("--dry-run", action="store_true", help="Immer JSON-Report ausgeben")
    args = parser.parse_args()

    env_path = Path(args.env_file)
    try:
        env = _parse_env_file(env_path)
    except FileNotFoundError as exc:
        print(json.dumps({"verdict": "FAIL", "error": str(exc)}, indent=2))
        return 2

    result = evaluate(env)
    print(json.dumps({"env_file": str(env_path), **result}, indent=2))

    verdict = str(result["verdict"])
    if verdict == "PASS":
        return 0
    if args.strict:
        return 2 if verdict == "FAIL" else 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
