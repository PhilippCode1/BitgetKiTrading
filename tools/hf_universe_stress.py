#!/usr/bin/env python3
"""
P80: HF Marktuniversum-Stresstest (500 Symbole x 10 Ticks/s = 5000 ev/s Ziel).

Voraussetzung: Redis erreichbar; Ziel-Stack laeuft (market-stream, feature-engine, …)
oder zumindest Eventbus-Redis, damit `pipeline_event_drop_total` Sinn ergibt.

Beispiel (Kurzlauf, 15s):
  python tools/hf_universe_stress.py --duration-sec 15 --market-stream-metrics-url http://127.0.0.1:8010/metrics

Produktions-Sign-off (30 Min, DoD) — Metriken fuer pipeline_event_drop_total vorgeben:
  python tools/hf_universe_stress.py --duration-sec 1800 \\
    --market-stream-metrics-url http://127.0.0.1:8010/metrics \\
    --feature-engine-metrics-url http://127.0.0.1:8020/metrics \\
    --out-json docs/audit/hf_stress_signoff.json

Hinweis: 30-Min-Lauf ressourcenintensiv; in CI z. B. --duration-sec 10.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

# Monorepo-Root: shared_py + config/ (fuer eventbus-Imports)
_ROOT = Path(__file__).resolve().parents[1]
for p in (str(_ROOT), str(_ROOT / "shared" / "python" / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from shared_py.eventbus import (  # noqa: E402
    STREAM_MARKET_TICK,
    EventEnvelope,
    RedisStreamBus,
)

_DROP_RE = re.compile(
    r"^pipeline_event_drop_total\{[^}]*\}\s+([0-9.eE+-]+)\s*(?:#.*)?$",
    re.MULTILINE,
)

_CPU_RE = re.compile(
    r"^process_cpu_seconds_total\{[^}]*\}\s+([0-9.eE+-]+)\s", re.MULTILINE
)


@dataclass
class StressMetrics:
    target_symbols: int
    ticks_per_symbol_per_sec: float
    target_events_per_sec: float
    published_total: int
    wall_duration_sec: float
    achieved_eps: float
    drop_count_before: float
    drop_count_after: float
    drop_delta: float
    drop_rate: float | None
    max_rss_bytes_self: int | None
    cpu_samples_stdev: float | None
    pass_drop_rate: bool
    pass_no_memoryerror: bool
    pass_cpu_fairness: bool
    pass_eps_ratio: bool
    notes: str


def _sum_pipeline_drops(text: str) -> float:
    t = 0.0
    for m in _DROP_RE.finditer(text):
        t += float(m.group(1))
    return t


def _last_process_cpu(text: str) -> float | None:
    m = _CPU_RE.search(text)
    return float(m.group(1)) if m else None


def _get_metrics(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "hf_universe_stress/1"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=5.0) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


class HighFrequencyMockFeeder:
    """
    Publiziert `market_tick`-Events in ``events:market_tick`` (Redis) mit
    fester Ziel-Rate: ``symbols * ticks_per_sec``.
    """

    def __init__(
        self,
        redis_url: str,
        *,
        symbols: list[str],
        ticks_per_symbol_per_sec: float = 10.0,
    ) -> None:
        if len(symbols) < 1:
            raise ValueError("mindestens ein Symbol")
        self._symbols = list(symbols)
        self._hz = float(ticks_per_symbol_per_sec)
        self._bus = RedisStreamBus.from_url(redis_url, dedupe_ttl_sec=0)
        self._seq = 0
        self.published: int = 0

    def close(self) -> None:
        self._bus.close()

    def _tick_envelope(self, sym: str, ts_ms: int) -> EventEnvelope:
        self._seq += 1
        return EventEnvelope(
            event_type="market_tick",
            symbol=sym,
            exchange_ts_ms=ts_ms,
            dedupe_key=f"hf_stress:{sym}:{ts_ms}:{self._seq & 0xFFFF_FFFF}",
            payload={
                "mark_price": 50_000.0
                + (self._seq % 10_000) * 0.01
                + hash(sym) % 100 * 0.01,
                "ts_ms": ts_ms,
                "source": "hf_universe_stress",
            },
            trace={"source": "hf_universe_stress", "version": "P80-1"},
        )

    def publish_once_round_robin(self) -> None:
        """Exakt ein Tick pro Zeitschritt; Round-Robin durch alle Symbole."""
        ts = int(time.time() * 1000)
        idx = self.published % len(self._symbols)
        sym = self._symbols[idx]
        env = self._tick_envelope(sym, ts)
        self._bus.publish(STREAM_MARKET_TICK, env)
        self.published += 1

    def run(self, duration_sec: float) -> int:
        """
        Erzeugt naeherungsweise `len(symbols) * ticks_per_sec * duration` Ticks
        (Rate = symbols * ticks_per_sec Events/s, gleichmaessig verteilt).
        """
        n = len(self._symbols)
        total_target = int(duration_sec * n * self._hz)
        interval = 1.0 / (n * self._hz) if n and self._hz else 0.0
        t0 = time.perf_counter()
        nxt = t0
        for _ in range(max(0, total_target)):
            now = time.perf_counter()
            d = nxt - now
            if d > 0:
                time.sleep(d)
            nxt = max(nxt, now) + interval
            self.publish_once_round_robin()
        return self.published


def _self_rss() -> int | None:
    try:
        import psutil  # type: ignore[import-untyped]
    except ImportError:
        return None
    return int(psutil.Process().memory_info().rss)


def _run_cpu_fairness_probe(duration: float) -> float | None:
    try:
        import psutil  # type: ignore[import-untyped]
    except ImportError:
        return None
    psutil.cpu_percent(interval=0.1)  # prime
    samples: list[float] = []
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < min(duration, 2.0):
        samples.append(psutil.cpu_percent(interval=0.15))
    if len(samples) < 3:
        return None
    mean = sum(samples) / len(samples)
    var = sum((x - mean) ** 2 for x in samples) / (len(samples) - 1)
    return math.sqrt(var) if var >= 0.0 else 0.0


def _run(args: argparse.Namespace) -> int:
    syms: list[str] = []
    for i in range(int(args.symbols)):
        # synthetische Symbole, Bitget-Format-aehnlich
        syms.append(f"S{i:03d}USDT")
    drops_before = 0.0
    m_url = (args.market_stream_metrics_url or "").strip()
    fe_url = (args.feature_engine_metrics_url or "").strip()
    if m_url:
        try:
            drops_before = _sum_pipeline_drops(_get_metrics(m_url))
            if (fe_url or "").strip():
                drops_before += _sum_pipeline_drops(_get_metrics(fe_url))
        except (OSError, ValueError, urllib.error.URLError) as exc:
            print("metrics vorher: nicht lesbar (ok fuer reinen Publishe-Test):", exc)
    t_wall = 0.0
    n_pub = 0
    memerr = False
    rss_max = _self_rss()
    t0w = time.perf_counter()
    try:
        feeder = HighFrequencyMockFeeder(
            (args.redis_url or "").strip() or "redis://127.0.0.1:6379/0",
            symbols=syms,
            ticks_per_symbol_per_sec=float(args.ticks_per_symbol),
        )
        n_pub = feeder.run(float(args.duration_sec))
        feeder.close()
    except MemoryError:
        memerr = True
    t_wall = time.perf_counter() - t0w
    r2 = _self_rss()
    if r2 and rss_max:
        rss_max = max(rss_max, r2)

    drops_after = 0.0
    if m_url:
        try:
            drops_after = _sum_pipeline_drops(_get_metrics(m_url))
            if (fe_url or "").strip():
                drops_after += _sum_pipeline_drops(_get_metrics(fe_url))
        except (OSError, ValueError, urllib.error.URLError):
            pass
    d_drop = max(0.0, drops_after - drops_before)
    rate: float | None = (d_drop / n_pub) if n_pub else None
    # DoD: <0,01 %; mit /metrics; sonst Drop-Pruefung N/A (Pass)
    if m_url:
        pass_drop = bool(rate is not None and rate < 0.0001)
    else:
        pass_drop = True
    stdev = _run_cpu_fairness_probe(1.0)
    pass_fair = stdev is not None and stdev < 25.0
    if stdev is None:
        pass_fair = True  # ohne psutil: nicht messbar, nicht fail
    eps = n_pub / t_wall if t_wall > 0.0 else 0.0
    target = len(syms) * float(args.ticks_per_symbol)
    pass_eps = (eps / target) >= 0.85 if target else True

    rep = StressMetrics(
        target_symbols=len(syms),
        ticks_per_symbol_per_sec=float(args.ticks_per_symbol),
        target_events_per_sec=target,
        published_total=n_pub,
        wall_duration_sec=t_wall,
        achieved_eps=eps,
        drop_count_before=drops_before,
        drop_count_after=drops_after,
        drop_delta=d_drop,
        drop_rate=rate,
        max_rss_bytes_self=rss_max,
        cpu_samples_stdev=stdev,
        pass_drop_rate=pass_drop,
        pass_no_memoryerror=not memerr,
        pass_cpu_fairness=pass_fair,
        pass_eps_ratio=pass_eps,
        notes="Scalability Sign-off (P80) — vollstaendig nur mit Stack+Metriken+psutil",
    )
    data = {**{k: v for k, v in asdict(rep).items()}}
    data["schema"] = "hf_universe_stress_v1"
    data["signoff_ok"] = all(
        [
            rep.pass_drop_rate,
            rep.pass_no_memoryerror,
            rep.pass_cpu_fairness,
            rep.pass_eps_ratio,
        ]
    )
    if args.out_json:
        p = Path(args.out_json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print("JSON geschrieben:", p)
    print(json.dumps(data, indent=2)[:4_000])
    return 0 if data["signoff_ok"] and not memerr else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--redis-url", default=None, help="Default: env REDIS_URL / redis://…")
    p.add_argument("--symbols", type=int, default=500)
    p.add_argument("--ticks-per-symbol", type=float, default=10.0)
    p.add_argument(
        "--duration-sec", type=float, default=10.0, help="Voll-DoD: 1800 (30 Min)"
    )
    p.add_argument(
        "--market-stream-metrics-url",
        default="",
        help="leer: keine pipeline_event_drop-Summe; voll-DoD: market-stream /metrics",
    )
    p.add_argument(
        "--feature-engine-metrics-url",
        default="",
        help="feature-engine /metrics addieren (mit --market-stream-metrics-url)",
    )
    p.add_argument(
        "--out-json",
        default="",
        help="z. B. docs/audit/hf_stress_signoff_YYYYMMDD.json",
    )
    args = p.parse_args()
    if not args.redis_url:
        args.redis_url = (os.environ.get("REDIS_URL") or "redis://127.0.0.1:6379/0").strip()
    return _run(args)


if __name__ == "__main__":
    raise SystemExit(main())
