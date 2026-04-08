from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import psycopg
import redis


def _split_peer_urls(raw: str) -> list[str]:
    return [p.strip() for p in str(raw or "").split(",") if p.strip()]


def _evaluate_ready_payload(payload: dict[str, Any]) -> tuple[bool, str]:
    """True nur wenn ready=true und keine verschachtelten checks mit ok=false."""
    if payload.get("ready") is not True:
        return False, f"ready_not_true:{list(payload.keys())[:6]!r}"
    checks = payload.get("checks") or {}
    if isinstance(checks, dict):
        for _k, value in checks.items():
            if isinstance(value, dict):
                inner = value.get("ok")
                if inner is False:
                    return False, f"nested_check_failed:{_k}"
    return True, "ok"


def check_http_ready_json(url: str, *, timeout_sec: float = 2.5) -> tuple[bool, str]:
    """GET URL; JSON mit \"ready\": true. Fester Timeout, kein Jitter.

    HTTP 4xx/5xx: versucht JSON-Body zu lesen (z. B. Gateway liefert Details bei ready=false).
    """
    u = str(url or "").strip()
    if not u:
        return False, "empty_url"
    try:
        req = urllib.request.Request(
            u,
            method="GET",
            headers={"User-Agent": "readiness-probe/1"},
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw_body = resp.read(12_288)
        payload = json.loads(raw_body.decode("utf-8"))
        if not isinstance(payload, dict):
            return False, "non_object_json"
        ok, detail = _evaluate_ready_payload(payload)
        if ok:
            return True, "ok"
        return False, detail
    except urllib.error.HTTPError as e:
        try:
            raw_body = e.read(12_288)
            payload = json.loads(raw_body.decode("utf-8"))
            if isinstance(payload, dict):
                ok, detail = _evaluate_ready_payload(payload)
                if ok:
                    return True, "ok"
                return False, f"http_{e.code}:{detail}"
        except Exception:
            pass
        return False, f"http_{e.code}"
    except Exception as exc:
        return False, str(exc)[:200]


def append_peer_readiness_checks(
    parts: dict[str, tuple[bool, str]],
    peer_urls_raw: str,
    *,
    timeout_sec: float = 2.5,
) -> dict[str, tuple[bool, str]]:
    """Erweitert parts um upstream_0.. fuer kommagetrennte /ready-URLs.

    Peer-Requests laufen parallel (ThreadPool), Wartezeit ~ ein Timeout — kein Jitter.
    """
    urls = _split_peer_urls(peer_urls_raw)
    out = dict(parts)
    if not urls:
        return out
    workers = min(8, len(urls))
    indexed: dict[int, tuple[bool, str, str]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {
            pool.submit(check_http_ready_json, url, timeout_sec=timeout_sec): (i, url)
            for i, url in enumerate(urls)
        }
        for fut in as_completed(future_map):
            i, url = future_map[fut]
            try:
                ok, detail = fut.result()
            except Exception as exc:
                ok, detail = False, str(exc)[:200]
            indexed[i] = (ok, detail, url)
    for i in range(len(urls)):
        ok, detail, url = indexed[i]
        out[f"upstream_{i}"] = (ok, f"{url} -> {detail}")
    return out


def check_postgres(dsn: str, *, timeout_sec: float = 3.0) -> tuple[bool, str]:
    try:
        with psycopg.connect(dsn, connect_timeout=timeout_sec) as conn:
            conn.execute("SELECT 1")
        return True, "ok"
    except Exception as exc:
        return False, str(exc)[:200]


def check_redis_url(
    url: str,
    *,
    timeout_sec: float = 2.0,
    retries: int = 0,
) -> tuple[bool, str]:
    """Redis PING mit optionalem Retry (transiente Socket-/Timeouts).

    `retries` = zusaetzliche Versuche nach dem ersten (insgesamt 1 + retries).
    Kurzer Backoff zwischen Versuchen (Docker/Netz-Flakes).
    """
    u = str(url or "").strip()
    if not u:
        return False, "empty_redis_url"
    attempts = max(1, int(retries) + 1)
    last_err = "ping_failed"
    for attempt in range(attempts):
        client: redis.Redis | None = None
        try:
            client = redis.Redis.from_url(
                u,
                socket_connect_timeout=timeout_sec,
                socket_timeout=timeout_sec,
                health_check_interval=0,
            )
            if client.ping():
                return True, "ok"
            last_err = "ping_failed"
        except Exception as exc:
            last_err = str(exc)[:200]
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
        if attempt + 1 < attempts:
            time.sleep(0.05 * float(attempt + 1))
    return False, last_err


def merge_ready_details(parts: dict[str, tuple[bool, str]]) -> tuple[bool, dict[str, Any]]:
    ok = all(p[0] for p in parts.values())
    details = {k: {"ok": v[0], "detail": v[1]} for k, v in parts.items()}
    return ok, details
