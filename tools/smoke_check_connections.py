#!/usr/bin/env python3
"""Smoke: ENV-Praesenz, Settings laden, Leverage/Futures-Konsistenz — keine Netzwerk-Calls, keine Secrets."""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")


def _ok(msg: str) -> None:
    print(f"OK: {msg}")


def _present(name: str) -> bool:
    v = (os.environ.get(name) or "").strip()
    if not v:
        return False
    if v.startswith("<") and v.endswith(">"):
        return False
    upper = v.upper()
    if "SET_ME" in upper or upper == "<SET_ME>":
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        default=".env.local",
        help="Relativer Pfad unter Repo-Root; setzt CONFIG_ENV_FILE absolut vor Settings-Import.",
    )
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    rs = str(repo)
    if rs not in sys.path:
        sys.path.insert(0, rs)
    os.chdir(repo)
    rel = args.env_file.strip().lstrip("/\\")
    abs_path = (repo / rel).resolve()
    if not abs_path.is_file():
        _fail(f"env-Datei fehlt: {rel}")
        return 1
    os.environ["CONFIG_ENV_FILE"] = str(abs_path)

    import config.paths as paths_mod

    importlib.reload(paths_mod)
    import config.settings as settings_mod

    importlib.reload(settings_mod)
    from config.settings import BaseServiceSettings

    try:
        s = BaseServiceSettings()
    except Exception as exc:
        _fail(f"BaseServiceSettings: {type(exc).__name__}")
        return 1
    _ok("BaseServiceSettings geladen")

    if not s.llm_use_fake_provider:
        missing = [k for k in ("OPENAI_API_KEY",) if not _present(k)]
        if missing:
            _fail(f"OpenAI: fehlen oder Platzhalter ({', '.join(missing)})")
            return 1
        _ok("OpenAI-Schluessel gesetzt (non-empty)")
    else:
        _ok("LLM_USE_FAKE_PROVIDER=true — OPENAI_API_KEY optional")

    for label, keys in (("Bitget", ("BITGET_API_KEY", "BITGET_API_SECRET", "BITGET_API_PASSPHRASE")),):
        missing = [k for k in keys if not _present(k)]
        if missing:
            _fail(f"{label}: fehlen oder Platzhalter ({', '.join(missing)})")
            return 1
        _ok(f"{label} Schluessel gesetzt (non-empty)")

    max_lv = s.risk_allowed_leverage_max
    for name in (
        "leverage_family_max_cap_spot",
        "leverage_family_max_cap_margin",
        "leverage_family_max_cap_futures",
    ):
        cap = getattr(s, name)
        if cap > max_lv:
            _fail(f"{name} > RISK_ALLOWED_LEVERAGE_MAX")
            return 1
    _ok("Leverage-Caps <= RISK_ALLOWED_LEVERAGE_MAX")

    pt = (s.bitget_futures_default_product_type or "").strip().upper()
    allowed = s.bitget_futures_allowed_product_types_list()
    if pt and allowed and pt not in allowed:
        _fail("BITGET_FUTURES_DEFAULT_PRODUCT_TYPE nicht in BITGET_FUTURES_ALLOWED_PRODUCT_TYPES")
        return 1
    _ok("Futures Produkttyp konsistent (falls gesetzt)")

    mf = (os.environ.get("BITGET_MARKET_FAMILY") or "").strip().lower()
    if pt == "USDT-FUTURES" and mf and mf not in ("futures", "mix", ""):
        _fail("BITGET_MARKET_FAMILY widerspricht USDT-FUTURES")
        return 1
    _ok("Bitget Market-Family plausibel (falls gesetzt)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
