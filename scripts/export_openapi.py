#!/usr/bin/env python3
"""
Schreibt die FastAPI-OpenAPI-Spezifikation des API-Gateways nach
shared/contracts/openapi/api-gateway.openapi.json (ohne laufenden Server).

Nutzt dieselbe Pflicht-ENV-Belegung wie tests/unit/contracts/test_openapi_export_sync.py,
damit der Export ohne .env.local reproduzierbar ist.

Aus Repo-Root:
  python scripts/export_openapi.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _openapi_test_env_value(name: str) -> str:
    u = name.upper()
    if "DATABASE_URL" in u:
        return "postgresql://u:p@localhost:5432/db"
    if "REDIS_URL" in u:
        return "redis://localhost:6379/0"
    return "ci_repeatable_secret_min_32_chars_x"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "shared" / "python" / "src"))

    from config.required_secrets import required_env_names_for_env_file_profile

    for key in required_env_names_for_env_file_profile(profile="local"):
        os.environ.setdefault(key, _openapi_test_env_value(key))
    os.environ.setdefault("PRODUCTION", "false")
    os.environ.setdefault("APP_ENV", "local")
    os.environ.setdefault("EXECUTION_MODE", "paper")
    os.environ.setdefault("SHADOW_TRADE_ENABLE", "false")
    os.environ.setdefault("LIVE_TRADE_ENABLE", "false")
    os.environ.setdefault("LIVE_BROKER_ENABLED", "false")
    os.environ.setdefault("STRATEGY_EXEC_MODE", "manual")
    os.environ.setdefault("RISK_HARD_GATING_ENABLED", "true")
    os.environ.setdefault("RISK_REQUIRE_7X_APPROVAL", "true")
    os.environ.setdefault("RISK_ALLOWED_LEVERAGE_MIN", "7")
    os.environ.setdefault("RISK_ALLOWED_LEVERAGE_MAX", "75")
    os.environ.setdefault("LIVE_KILL_SWITCH_ENABLED", "true")
    os.environ.setdefault("CORS_ALLOW_ORIGINS", "http://localhost:3000")
    os.environ.setdefault("APP_BASE_URL", "http://localhost:8000")
    os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
    os.environ.setdefault("COMMERCIAL_ENABLED", "false")

    sys.path.insert(0, str(root / "services" / "api-gateway" / "src"))

    import config.gateway_settings as gw_mod

    gw_mod.get_gateway_settings.cache_clear()
    for mod in list(sys.modules):
        if mod == "api_gateway.app" or mod.startswith("api_gateway."):
            del sys.modules[mod]

    from api_gateway.app import app  # noqa: PLC0415

    out_dir = root / "shared" / "contracts" / "openapi"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "api-gateway.openapi.json"
    out_path.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"geschrieben: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
