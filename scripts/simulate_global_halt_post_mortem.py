#!/usr/bin/env python3
"""
P79 DoD: setzt `system:global_halt` in Redis und führt einen Post-Mortem-Lauf aus
(Stack: monitor-engine Konfig, llm-orchestrator mit FAKE, Postgres Migration 630).

Nutzung (Repo-Root, ENV gesetzt: REDIS_URL, DATABASE_URL, INTERNAL_API_KEY, …):

  PYTHONPATH=shared/python/src;services/monitor-engine/src
  python scripts/simulate_global_halt_post_mortem.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _bootstrap_path() -> None:
    r = str(ROOT)
    s = str(ROOT / "shared" / "python" / "src")
    s2 = str(ROOT / "services" / "monitor-engine" / "src")
    for p in (r, s, s2):
        if p not in sys.path:
            sys.path.insert(0, p)


def main() -> int:
    _bootstrap_path()
    p = argparse.ArgumentParser()
    p.add_argument(
        "--no-set-redis",
        action="store_true",
        help="Nur run_incident, kein SET in Redis (Trigger schon manuell)",
    )
    a = p.parse_args()

    from config.bootstrap import bootstrap_from_settings

    from monitor_engine.config import MonitorEngineSettings
    from monitor_engine.incident_rca.post_mortem import run_incident_post_mortem_once
    from shared_py.eventbus import RedisStreamBus
    from shared_py.observability.global_halt_redis import (
        PUB_CHANNEL_GLOBAL_HALT,
        REDIS_KEY_GLOBAL_HALT,
    )

    settings = MonitorEngineSettings()
    bootstrap_from_settings("monitor-engine", settings)
    ru = (os.environ.get("REDIS_URL") or "").strip()
    if not ru and not a.no_set_redis:
        print("REDIS_URL fehlt", file=sys.stderr)
        return 2
    t0 = time.perf_counter()
    bus = RedisStreamBus.from_url(ru, dedupe_ttl_sec=0)
    try:
        r = bus.redis
        if not a.no_set_redis:
            r.set(REDIS_KEY_GLOBAL_HALT, "1")
            r.publish(PUB_CHANNEL_GLOBAL_HALT, "1")
        try:
            pm = asyncio.run(
                run_incident_post_mortem_once(settings, bus, time_budget_sec=9.0)
            )
        finally:
            if not a.no_set_redis:
                r.set(REDIS_KEY_GLOBAL_HALT, "0")
                r.publish(PUB_CHANNEL_GLOBAL_HALT, "0")
    finally:
        bus.close()
    elapsed = time.perf_counter() - t0
    me = f"http://127.0.0.1:{settings.monitor_engine_port}"
    print(
        f"ok post_mortem_id={pm} wall_ms={int(elapsed * 1000)}"
    )
    print(
        f"GET: {me}/ops/post-mortems/{pm}  "
        f"(X-Internal-Service-Key, ggf. Operator-JWT am Gateway)"
    )
    if elapsed > 10.0:
        print("WARN: >10s (LLM/Health langsam; Tests mit Mocks: <1s)", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
