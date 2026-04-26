#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_EXACT = {
    "EXECUTION_MODE": "bitget_demo",
    "LIVE_TRADE_ENABLE": "false",
    "BITGET_DEMO_ENABLED": "true",
    "DEMO_ORDER_SUBMIT_ENABLE": "false",
    "DEMO_CLOSE_POSITION_ENABLE": "false",
    "BITGET_DEMO_PAPTRADING_HEADER": "1",
}

REQUIRED_NON_EMPTY = (
    "APP_BASE_URL",
    "FRONTEND_URL",
    "CORS_ALLOW_ORIGINS",
    "NEXT_PUBLIC_API_BASE_URL",
    "NEXT_PUBLIC_WS_BASE_URL",
    "POSTGRES_PASSWORD",
    "GRAFANA_ADMIN_PASSWORD",
)

LIVE_KEYS_MUST_BE_EMPTY = (
    "BITGET_API_KEY",
    "BITGET_API_SECRET",
    "BITGET_API_PASSPHRASE",
)

DEMO_SECRET_KEYS = (
    "BITGET_DEMO_API_KEY",
    "BITGET_DEMO_API_SECRET",
    "BITGET_DEMO_API_PASSPHRASE",
)

SAFETY_FLAGS_MUST_BE_FALSE = (
    "private_live_allowed",
    "full_autonomous_live",
)

_PLACEHOLDER_MARKERS = (
    "<set_me>",
    "change_me",
    "changeme",
    "example",
    "your_api_key_here",
    "redacted",
    "dummy",
    "placeholder",
)


@dataclass
class DemoEnvComposeGateReport:
    result: str
    blockers: list[str]
    warnings: list[str]
    checks: dict[str, Any]
    compose_available: bool


def _parse_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _run_command(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
    )


def _is_placeholder_or_empty(value: str) -> bool:
    v = value.strip()
    if not v:
        return True
    low = v.lower()
    return any(marker in low for marker in _PLACEHOLDER_MARKERS)


def _contains_missing_var_warning(stderr: str) -> bool:
    return 'variable is not set. Defaulting to a blank string' in (stderr or "")


def build_gate_report(env_file: Path, check_full_config: bool = True) -> DemoEnvComposeGateReport:
    blockers: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}

    if not env_file.is_file():
        return DemoEnvComposeGateReport(
            result="FAIL",
            blockers=[f"ENV-Datei fehlt: {env_file}"],
            warnings=[],
            checks={"env_file_exists": False},
            compose_available=False,
        )

    checks["env_file_exists"] = True
    checks["env_file"] = str(env_file)
    data = _parse_env_file(env_file)

    # .env.demo darf nie committed sein.
    tracked = _run_command(["git", "ls-files", "--error-unmatch", ".env.demo"], cwd=ROOT)
    checks["env_demo_committed"] = tracked.returncode == 0
    if tracked.returncode == 0:
        blockers.append(".env.demo ist im Git-Index tracked; muss untracked bleiben.")

    for key, expected in REQUIRED_EXACT.items():
        val = data.get(key, "")
        checks[f"{key}_ok"] = val == expected
        if val != expected:
            blockers.append(f"{key} muss '{expected}' sein.")

    for key in REQUIRED_NON_EMPTY:
        val = data.get(key, "")
        checks[f"{key}_present"] = bool(val.strip())
        if not val.strip():
            blockers.append(f"{key} fehlt oder ist leer.")

    for key in LIVE_KEYS_MUST_BE_EMPTY:
        val = data.get(key, "")
        checks[f"{key}_empty"] = (val.strip() == "")
        if val.strip():
            blockers.append(f"{key} muss im Demo-Profil leer sein.")

    for key in DEMO_SECRET_KEYS:
        val = data.get(key, "")
        checks[f"{key}_placeholder_or_empty"] = _is_placeholder_or_empty(val)
        if not _is_placeholder_or_empty(val):
            blockers.append(f"{key} sieht nicht nach Platzhalter aus (moeglicher echter Secret-Wert).")

    for key in SAFETY_FLAGS_MUST_BE_FALSE:
        if key in data:
            checks[f"{key}_false"] = data.get(key, "").strip().lower() == "false"
            if data.get(key, "").strip().lower() != "false":
                blockers.append(f"{key} muss false bleiben.")

    docker_check = _run_command(["docker", "compose", "version"], cwd=ROOT)
    compose_available = docker_check.returncode == 0
    checks["compose_available"] = compose_available

    if compose_available:
        services = _run_command(
            ["docker", "compose", "--env-file", str(env_file), "config", "--services"],
            cwd=ROOT,
        )
        checks["compose_config_services_exit_code"] = services.returncode
        if services.returncode != 0:
            blockers.append("docker compose config --services ist fehlgeschlagen.")
        if _contains_missing_var_warning(services.stderr):
            blockers.append("Compose meldet fehlende ENV-Variablen in config --services.")

        if check_full_config:
            full_cfg = _run_command(
                ["docker", "compose", "--env-file", str(env_file), "config"],
                cwd=ROOT,
            )
            checks["compose_config_exit_code"] = full_cfg.returncode
            if full_cfg.returncode != 0:
                blockers.append("docker compose config ist fehlgeschlagen.")
            if _contains_missing_var_warning(full_cfg.stderr):
                blockers.append("Compose meldet fehlende ENV-Variablen in config.")
    else:
        warnings.append("docker compose nicht verfuegbar; Compose-Checks wurden uebersprungen.")
        checks["compose_checks"] = "SKIPPED_WITH_REASON"

    result = "FAIL" if blockers else "PASS"
    return DemoEnvComposeGateReport(
        result=result,
        blockers=blockers,
        warnings=warnings,
        checks=checks,
        compose_available=compose_available,
    )


def to_markdown(rep: DemoEnvComposeGateReport) -> str:
    lines = [
        "# CI Demo ENV Compose Gate",
        "",
        f"- Ergebnis: `{rep.result}`",
        f"- Compose verfuegbar: `{str(rep.compose_available).lower()}`",
        "",
        "## Checks",
        *[f"- `{k}`: `{v}`" for k, v in sorted(rep.checks.items())],
        "",
        "## Blocker",
        *([f"- {b}" for b in rep.blockers] if rep.blockers else ["- keine"]),
        "",
        "## Warnungen",
        *([f"- {w}" for w in rep.warnings] if rep.warnings else ["- keine"]),
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=Path(".env.demo.example"))
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("reports/ci_demo_env_compose_gate.md"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("reports/ci_demo_env_compose_gate.json"),
    )
    parser.add_argument("--no-full-config", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = build_gate_report(
        env_file=args.env_file,
        check_full_config=not args.no_full_config,
    )
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(to_markdown(report), encoding="utf-8")
    args.output_json.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"ci_demo_env_compose_gate: result={report.result}")
    return 1 if report.result == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
