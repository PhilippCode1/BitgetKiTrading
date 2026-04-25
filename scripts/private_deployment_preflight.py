#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

Mode = Literal[
    "local_private",
    "local_ngrok_preview",
    "shadow_private",
    "staging_private",
    "production_private",
]

MODES: tuple[Mode, ...] = (
    "local_private",
    "local_ngrok_preview",
    "shadow_private",
    "staging_private",
    "production_private",
)

SENSITIVE_KEYS = ("secret", "token", "password", "authorization", "api_key", "passphrase", "jwt")


def parse_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        k, v = raw.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def _bool(env: dict[str, str], key: str, default: bool = False) -> bool:
    return env.get(key, str(default)).strip().lower() == "true"


def _is_localhost_url(url: str) -> bool:
    if not url:
        return False
    try:
        host = (urlparse(url).hostname or "").lower()
        return host in {"localhost", "127.0.0.1", "::1"}
    except Exception:
        return False


def _is_ngrok_url(url: str) -> bool:
    lowered = url.lower()
    return "ngrok" in lowered


def _contains_secret(text: str) -> bool:
    low = text.lower()
    return any(k in low for k in SENSITIVE_KEYS)


def evaluate_mode(env: dict[str, str], mode: Mode) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    warnings: list[str] = []
    frontend_url = env.get("FRONTEND_URL", "").strip()
    app_base_url = env.get("APP_BASE_URL", "").strip()
    cors = env.get("CORS_ALLOW_ORIGINS", "").strip()
    debug = _bool(env, "DEBUG")
    live = _bool(env, "LIVE_TRADE_ENABLE")
    api_auth_mode = env.get("API_AUTH_MODE", "").strip().lower()
    dashboard_auth = env.get("DASHBOARD_GATEWAY_AUTHORIZATION", "").strip()
    allow_event_debug = _bool(env, "SECURITY_ALLOW_EVENT_DEBUG_ROUTES")
    allow_db_debug = _bool(env, "SECURITY_ALLOW_DB_DEBUG_ROUTES")
    allow_alert_replay = _bool(env, "SECURITY_ALLOW_ALERT_REPLAY_ROUTES")

    ngrok_detected = _is_ngrok_url(frontend_url) or _is_ngrok_url(app_base_url)
    auth_ok = bool(dashboard_auth) or api_auth_mode in {"api_key", "jwt", "bearer"}
    cors_wildcard = cors == "*" or "*" in [x.strip() for x in cors.split(",") if x.strip()]

    if mode == "local_ngrok_preview":
        if not ngrok_detected:
            issues.append(
                {
                    "code": "ngrok_expected_missing",
                    "message": "Mode local_ngrok_preview erwartet ngrok-URL in FRONTEND_URL oder APP_BASE_URL.",
                }
            )
        if not auth_ok:
            issues.append({"code": "ngrok_auth_missing", "message": "ngrok-preview ohne Auth ist verboten."})
        if live:
            issues.append(
                {
                    "code": "ngrok_live_trade_enabled",
                    "message": "LIVE_TRADE_ENABLE=true ist in ngrok-preview blockierend verboten.",
                }
            )
        if allow_event_debug or allow_db_debug or allow_alert_replay:
            issues.append(
                {
                    "code": "ngrok_debug_routes_open",
                    "message": "Debug-Routen duerfen im ngrok-preview nicht offen sein.",
                }
            )
    if mode in {"staging_private", "production_private"}:
        if debug:
            issues.append({"code": "debug_enabled_in_sensitive_mode", "message": f"DEBUG=true ist in {mode} verboten."})
        if _is_localhost_url(frontend_url) or _is_localhost_url(app_base_url):
            issues.append({"code": "localhost_public_url_blocker", "message": "localhost/127.0.0.1 in sensitivem Profil ist Blocker."})
        if cors_wildcard:
            issues.append({"code": "cors_wildcard_sensitive_profile", "message": "CORS wildcard ist fuer sensitive Profile verboten."})
        if mode == "production_private" and (not frontend_url.startswith("https://") or not app_base_url.startswith("https://")):
            issues.append(
                {
                    "code": "production_https_required",
                    "message": "production_private braucht HTTPS fuer FRONTEND_URL und APP_BASE_URL.",
                }
            )
    if ngrok_detected and live:
        issues.append(
            {
                "code": "ngrok_live_combo_blocked",
                "message": "Ngrok/Public-Preview darf keine Live-Write-Freigabe haben.",
            }
        )
    if not auth_ok:
        warnings.append("Auth wirkt unvollstaendig; Main Console muss sensitive Bereiche blockieren.")

    if mode == "local_ngrok_preview":
        security_mode_de = "ngrok-preview mit harter Auth und blockiertem Live-Write."
    elif mode == "production_private":
        security_mode_de = "production_private mit HTTPS, server-only Auth und fail-closed Live-Gates."
    elif mode == "staging_private":
        security_mode_de = "staging_private mit produktionsnahen Sicherheitsregeln, Live standardmaessig blockiert."
    elif mode == "shadow_private":
        security_mode_de = "shadow_private: Shadow aktiv, echte Live-Orders bleiben blockiert."
    else:
        security_mode_de = "local_private: lokale Entwicklung, kein oeffentlicher Zugriff, Live blockiert."

    return {
        "mode": mode,
        "go": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "ngrok_detected": ngrok_detected,
        "auth_ok": auth_ok,
        "live_trade_enable": live,
        "debug_enabled": debug,
        "main_console_sicherheitsmodus_de": security_mode_de,
    }


def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False)
    if _contains_secret(text):
        # no secrets should be embedded; scrub aggressively
        return json.loads(
            json.dumps(payload, ensure_ascii=False)
            .replace("DASHBOARD_GATEWAY_AUTHORIZATION", "REDACTED_KEY")
            .replace("API_KEY", "REDACTED_KEY")
        )
    return payload


def to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Private Deployment Preflight",
        "",
        f"- Modus: `{payload['mode']}`",
        f"- Go/No-Go: `{'GO' if payload['go'] else 'NO_GO'}`",
        f"- ngrok erkannt: `{payload['ngrok_detected']}`",
        f"- Auth OK: `{payload['auth_ok']}`",
        f"- LIVE_TRADE_ENABLE: `{payload['live_trade_enable']}`",
        f"- DEBUG: `{payload['debug_enabled']}`",
        f"- Main-Console-Sicherheitsmodus: {payload['main_console_sicherheitsmodus_de']}",
        "",
        "## Probleme",
    ]
    issues = payload.get("issues", [])
    if issues:
        for issue in issues:
            lines.append(f"- `{issue.get('code')}`: {issue.get('message')}")
    else:
        lines.append("- Keine blockierenden Probleme gefunden.")
    lines.append("")
    lines.append("## Warnungen")
    warnings = payload.get("warnings", [])
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- Keine Warnungen.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deployment/ngrok/staging Preflight fuer private Runtime-Profile.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--env-file", default=".env.local")
    parser.add_argument("--mode", choices=list(MODES), default="local_private")
    parser.add_argument("--output-md")
    args = parser.parse_args(argv)

    if args.dry_run:
        payload = {
            "mode": args.mode,
            "dry_run": True,
            "go": True,
            "network_calls": 0,
            "main_console_sicherheitsmodus_de": "Dry-run: statische Pruefung, keine Netzwerkaktion, kein Order-Pfad.",
            "issues": [],
            "warnings": [],
        }
    else:
        env = parse_env_file(Path(args.env_file))
        payload = evaluate_mode(env, args.mode)
        payload["dry_run"] = False
        payload["network_calls"] = 0
    payload = sanitize_payload(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))

    if args.output_md:
        out = Path(args.output_md)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(to_markdown(payload), encoding="utf-8")

    return 0 if payload.get("go") else 1


if __name__ == "__main__":
    raise SystemExit(main())
