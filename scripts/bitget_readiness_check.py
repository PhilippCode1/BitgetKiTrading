#!/usr/bin/env python3
"""Safe read-only Bitget Exchange Readiness check.

Modes:
- dry-run: no network calls.
- readonly: public/private read-only requests only; never orders.
- demo-safe: demo credentials only, still read-only; never orders.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import httpx

from shared_py.bitget.exchange_readiness import (
    READINESS_CONTRACT_VERSION,
    WRITE_ORDER_ALLOWED_DEFAULT,
    assess_permissions,
    assert_readonly_request,
    classify_http_status,
    path_uses_legacy_v1,
    readiness_verdict,
    server_time_skew_blockers,
)
from shared_py.bitget.http import build_private_rest_headers, build_query_string

BITGET_BASE_URL = "https://api.bitget.com"
PUBLIC_TIME_PATH = "/api/v2/public/time"
SPOT_SYMBOLS_PATH = "/api/v2/spot/public/symbols"
FUTURES_CONTRACTS_PATH = "/api/v2/mix/market/contracts"
PRIVATE_SPOT_ASSETS_PATH = "/api/v2/spot/account/assets"
PRIVATE_FUTURES_ACCOUNT_PATH = "/api/v2/mix/account/accounts"
DOC_API_VERSION_PATHS = (
    PUBLIC_TIME_PATH,
    SPOT_SYMBOLS_PATH,
    FUTURES_CONTRACTS_PATH,
    PRIVATE_SPOT_ASSETS_PATH,
    PRIVATE_FUTURES_ACCOUNT_PATH,
)
PLACEHOLDER_MARKERS = (
    "<set_me>",
    "<changeme>",
    "changeme",
    "change_me",
    "set_me",
    "your_api_key_here",
    "your_secret_value_here",
    "placeholder",
)
SECRET_KEY_FRAGMENTS = ("SECRET", "TOKEN", "PASSWORD", "PASSPHRASE", "API_KEY", "ACCESS-KEY")


@dataclass
class StepStatus:
    status: str
    detail: str = ""
    http_status: int | None = None
    classification: str | None = None


@dataclass
class BitgetReadinessReport:
    contract_version: str
    generated_at: str
    git_sha: str
    mode: str
    env_profile: str
    credential_type: str
    credential_summary: dict[str, str]
    api_version_paths: list[str]
    public_api_status: StepStatus
    private_readonly_status: StepStatus
    permission_status: StepStatus
    instrument_universe_status: StepStatus
    product_mapping_status: StepStatus
    rate_limit_status: StepStatus
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    result: str = "FAIL"
    live_write_allowed: bool = WRITE_ORDER_ALLOWED_DEFAULT


def load_dotenv(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = _strip_inline_comment(value.strip())
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        env[key.strip()] = value
    return env


def _strip_inline_comment(value: str) -> str:
    in_single = False
    in_double = False
    out: list[str] = []
    for index, char in enumerate(value):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            if index == 0 or value[index - 1].isspace():
                break
        out.append(char)
    return "".join(out).strip()


def is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    lower = value.strip().lower()
    if not lower:
        return True
    if lower.startswith("bearer "):
        lower = lower[7:].strip()
    if lower.startswith("<") and lower.endswith(">"):
        return True
    return any(marker in lower for marker in PLACEHOLDER_MARKERS)


def truthy(env: dict[str, str], key: str) -> bool:
    return env.get(key, "").strip().lower() in {"1", "true", "yes", "on"}


def detect_profile(env: dict[str, str]) -> str:
    app_env = env.get("APP_ENV", "").strip().lower()
    if app_env:
        return app_env
    return "production" if truthy(env, "PRODUCTION") else "local"


def credential_type(env: dict[str, str]) -> str:
    live = any(not is_placeholder(env.get(key)) for key in ("BITGET_API_KEY", "BITGET_API_SECRET", "BITGET_API_PASSPHRASE"))
    demo = any(
        not is_placeholder(env.get(key))
        for key in ("BITGET_DEMO_API_KEY", "BITGET_DEMO_API_SECRET", "BITGET_DEMO_API_PASSPHRASE")
    )
    if live and demo:
        return "mixed"
    if demo or truthy(env, "BITGET_DEMO_ENABLED"):
        return "demo"
    if live:
        return "live"
    return "none"


def credential_summary(env: dict[str, str]) -> dict[str, str]:
    return {
        "live_key": _redacted_presence(env.get("BITGET_API_KEY")),
        "live_secret": _redacted_presence(env.get("BITGET_API_SECRET")),
        "live_passphrase": _redacted_presence(env.get("BITGET_API_PASSPHRASE")),
        "demo_key": _redacted_presence(env.get("BITGET_DEMO_API_KEY")),
        "demo_secret": _redacted_presence(env.get("BITGET_DEMO_API_SECRET")),
        "demo_passphrase": _redacted_presence(env.get("BITGET_DEMO_API_PASSPHRASE")),
    }


def _redacted_presence(value: str | None) -> str:
    if is_placeholder(value):
        return "missing_or_placeholder"
    return "set_redacted"


def redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for key, value in obj.items():
            if any(fragment in str(key).upper() for fragment in SECRET_KEY_FRAGMENTS):
                out[str(key)] = "[REDACTED]"
            else:
                out[str(key)] = redact(value)
        return out
    if isinstance(obj, list):
        return [redact(item) for item in obj]
    return obj


def git_sha() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip()
    except Exception:
        return "unknown"


class _MinimalBitgetSettings:
    def __init__(self, env: dict[str, str]) -> None:
        self.bitget_demo_enabled = truthy(env, "BITGET_DEMO_ENABLED")
        self.bitget_rest_locale = env.get("BITGET_REST_LOCALE", "en-US") or "en-US"
        self.bitget_demo_paptrading_header = env.get("BITGET_DEMO_PAPTRADING_HEADER", "1") or "1"
        self.effective_api_key = (
            env.get("BITGET_DEMO_API_KEY") if self.bitget_demo_enabled else env.get("BITGET_API_KEY")
        )
        self.effective_api_secret = (
            env.get("BITGET_DEMO_API_SECRET") if self.bitget_demo_enabled else env.get("BITGET_API_SECRET")
        )
        self.effective_api_passphrase = (
            env.get("BITGET_DEMO_API_PASSPHRASE")
            if self.bitget_demo_enabled
            else env.get("BITGET_API_PASSPHRASE")
        )

    def demo_headers(self) -> dict[str, str]:
        return {"paptrading": self.bitget_demo_paptrading_header} if self.bitget_demo_enabled else {}


def _get_json(client: httpx.Client, base_url: str, path: str, params: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
    assert_readonly_request("GET", path)
    response = client.get(f"{base_url}{path}", params=params)
    payload = response.json() if response.content else {}
    return response.status_code, payload if isinstance(payload, dict) else {"data": payload}


def _private_get_json(
    client: httpx.Client,
    base_url: str,
    path: str,
    env: dict[str, str],
    params: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    assert_readonly_request("GET", path)
    settings = _MinimalBitgetSettings(env)
    query_string = build_query_string(params)
    headers = build_private_rest_headers(
        settings,  # type: ignore[arg-type]
        timestamp_ms=int(datetime.now(tz=UTC).timestamp() * 1000),
        method="GET",
        request_path=path,
        query_string=query_string,
    )
    response = client.get(f"{base_url}{path}", params=params, headers=headers)
    payload = response.json() if response.content else {}
    return response.status_code, payload if isinstance(payload, dict) else {"data": payload}


def build_readiness_report(
    env: dict[str, str],
    *,
    mode: str,
    client: httpx.Client | None = None,
) -> BitgetReadinessReport:
    blockers: list[str] = []
    warnings: list[str] = []
    profile = detect_profile(env)
    cred_type = credential_type(env)
    base_url = (env.get("BITGET_API_BASE_URL") or BITGET_BASE_URL).rstrip("/")
    product_type = env.get("BITGET_PRODUCT_TYPE") or env.get("BITGET_FUTURES_DEFAULT_PRODUCT_TYPE") or "USDT-FUTURES"
    margin_coin = env.get("BITGET_MARGIN_COIN") or env.get("BITGET_FUTURES_DEFAULT_MARGIN_COIN") or "USDT"

    if cred_type == "mixed":
        blockers.append("demo_live_credential_mix")
    if mode == "demo-safe" and cred_type != "demo":
        blockers.append("demo_safe_requires_demo_credentials")
    if any(path_uses_legacy_v1(path) for path in DOC_API_VERSION_PATHS):
        blockers.append("legacy_v1_api_path_configured")
    else:
        warnings.append("api_version_v2_paths_documented_v1_usage_is_risk")

    if product_type == "COIN-FUTURES" and is_placeholder(margin_coin):
        blockers.append("coin_futures_requires_margin_coin")
    product_mapping_status = StepStatus(
        status="ready" if not any(b.startswith("coin_futures") for b in blockers) else "error",
        detail=f"productType={product_type}; marginCoin={margin_coin or 'missing'}",
    )

    public_api_status = StepStatus("unavailable", "dry-run: no network calls")
    private_status = StepStatus("unavailable", "dry-run: private read-only not executed")
    instrument_status = StepStatus("unavailable", "dry-run: instrument discovery not executed")
    rate_limit_status = StepStatus("ready", "no rate limit observed in dry-run")
    permission_status = StepStatus("degraded", "permission evidence missing; live write remains blocked")

    if mode == "dry-run":
        warnings.extend(
            [
                "dry_run_no_public_network_evidence",
                "dry_run_no_private_auth_evidence",
                "dry_run_no_instrument_universe_evidence",
                "permission_evidence_missing_live_write_blocked",
            ]
        )
    else:
        if client is None:
            client = httpx.Client(timeout=10.0)
            close_client = True
        else:
            close_client = False
        try:
            status, payload = _get_json(client, base_url, PUBLIC_TIME_PATH)
            classification = classify_http_status(status)
            if classification == "rate_limit":
                warnings.append("public_api_rate_limit")
            elif classification != "ok" or str(payload.get("code") or "00000") != "00000":
                blockers.append(f"public_api_{classification}")
            server_time = _extract_server_time(payload)
            offset_ms = None if server_time is None else server_time - int(datetime.now(tz=UTC).timestamp() * 1000)
            skew_blockers = server_time_skew_blockers(offset_ms)
            blockers.extend(skew_blockers)
            public_api_status = StepStatus(
                status="ready" if not skew_blockers and classification == "ok" else "error",
                detail=f"server_time_offset_ms={offset_ms if offset_ms is not None else 'unknown'}",
                http_status=status,
                classification=classification,
            )
            inst_status, inst_payload = _get_json(
                client,
                base_url,
                FUTURES_CONTRACTS_PATH,
                params={"productType": product_type},
            )
            inst_classification = classify_http_status(inst_status)
            if inst_classification == "rate_limit":
                warnings.append("instrument_rate_limit")
            elif inst_classification != "ok":
                blockers.append(f"instrument_universe_{inst_classification}")
            instrument_status = StepStatus(
                status="ready" if inst_classification == "ok" and bool(inst_payload) else "error",
                detail="instrument universe response received" if bool(inst_payload) else "instrument universe missing",
                http_status=inst_status,
                classification=inst_classification,
            )
            rate_limit_status = StepStatus(
                status="degraded" if "rate_limit" in {classification, inst_classification} else "ready",
                detail="rate limit observed" if "rate_limit" in {classification, inst_classification} else "no rate limit observed",
            )
            if cred_type in {"live", "demo"}:
                private_path = PRIVATE_FUTURES_ACCOUNT_PATH
                private_status_code, private_payload = _private_get_json(
                    client,
                    base_url,
                    private_path,
                    env,
                    params={"productType": product_type.lower()},
                )
                private_classification = classify_http_status(private_status_code)
                if private_classification == "rate_limit":
                    warnings.append("private_api_rate_limit")
                elif private_classification in {"auth", "permission"}:
                    blockers.append(f"private_api_{private_classification}")
                elif private_classification != "ok":
                    blockers.append(f"private_api_{private_classification}")
                private_status = StepStatus(
                    status="ready" if private_classification == "ok" else "error",
                    detail="private read-only response received",
                    http_status=private_status_code,
                    classification=private_classification,
                )
                perm = assess_permissions(_extract_permissions(private_payload))
            else:
                warnings.append("private_credentials_missing_readonly_skipped")
                perm = assess_permissions(None)
            blockers.extend(perm.blockers)
            warnings.extend(perm.warnings)
            permission_status = StepStatus(status=perm.status, detail=";".join(perm.blockers + perm.warnings) or "ok")
        except httpx.HTTPStatusError as exc:
            blockers.append(f"http_status_error:{exc.response.status_code}")
        except httpx.HTTPError as exc:
            blockers.append("bitget_transport_error")
            public_api_status = StepStatus("error", str(exc)[:180], classification="transport")
        finally:
            if close_client:
                client.close()

    result = readiness_verdict(blockers, warnings)
    return BitgetReadinessReport(
        contract_version=READINESS_CONTRACT_VERSION,
        generated_at=datetime.now(tz=UTC).isoformat(),
        git_sha=git_sha(),
        mode=mode,
        env_profile=profile,
        credential_type=cred_type,
        credential_summary=credential_summary(env),
        api_version_paths=list(DOC_API_VERSION_PATHS),
        public_api_status=public_api_status,
        private_readonly_status=private_status,
        permission_status=permission_status,
        instrument_universe_status=instrument_status,
        product_mapping_status=product_mapping_status,
        rate_limit_status=rate_limit_status,
        blockers=blockers,
        warnings=warnings,
        result=result,
        live_write_allowed=WRITE_ORDER_ALLOWED_DEFAULT,
    )


def _extract_server_time(payload: dict[str, Any]) -> int | None:
    data = payload.get("data")
    if isinstance(data, dict) and "serverTime" in data:
        try:
            return int(str(data["serverTime"]))
        except ValueError:
            return None
    if "serverTime" in payload:
        try:
            return int(str(payload["serverTime"]))
        except ValueError:
            return None
    return None


def _extract_permissions(payload: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("permissions", "permission", "authorities", "data"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return None


def report_to_markdown(report: BitgetReadinessReport) -> str:
    redacted = redact(asdict(report))
    lines = [
        "# Bitget Readiness Report",
        "",
        f"- Datum/Zeit: `{report.generated_at}`",
        f"- Git SHA: `{report.git_sha}`",
        f"- Modus: `{report.mode}`",
        f"- ENV-Profil: `{report.env_profile}`",
        f"- Credential-Typ: `{report.credential_type}`",
        f"- API-Version/Pfade: `{', '.join(report.api_version_paths)}`",
        f"- Public API Status: `{report.public_api_status.status}`",
        f"- Private Read-only Status: `{report.private_readonly_status.status}`",
        f"- Permission Status: `{report.permission_status.status}`",
        f"- Instrument Universe Status: `{report.instrument_universe_status.status}`",
        f"- ProductType/MarginCoin Mapping: `{report.product_mapping_status.status}`",
        f"- Rate Limit Status: `{report.rate_limit_status.status}`",
        f"- Ergebnis: `{report.result}`",
        f"- Live-Write erlaubt: `{str(report.live_write_allowed).lower()}`",
        "",
        "## Blocker",
        *(f"- `{item}`" for item in report.blockers),
        "",
        "## Warnings",
        *(f"- `{item}`" for item in report.warnings),
        "",
        "## Redacted JSON",
        "```json",
        json.dumps(redacted, indent=2, sort_keys=True, ensure_ascii=False),
        "```",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--mode", choices=("dry-run", "readonly", "demo-safe"), default="dry-run")
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not args.env_file.is_file():
        print(f"ERROR env_file_missing: {args.env_file}")
        return 1
    env = load_dotenv(args.env_file)
    report = build_readiness_report(env, mode=args.mode)
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(report_to_markdown(report), encoding="utf-8")
    payload = redact(asdict(report))
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(
            "bitget_readiness: "
            f"result={report.result} mode={report.mode} profile={report.env_profile} "
            f"credential_type={report.credential_type} live_write_allowed=false"
        )
        for blocker in report.blockers:
            print(f"BLOCKER {blocker}")
        for warning in report.warnings:
            print(f"WARNING {warning}")
    return 1 if report.result == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
