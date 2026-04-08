# P0-0 — Redis ↔ Gateway Readiness (Evidence)

**Datum:** 2026-04-08  
**Ziel:** `GET /ready` liefert `checks.redis.ok: true` / `summary.core_redis: true` zuverlässig; weniger Flakes durch `Timeout reading from socket`.

## Root Cause (kurz)

- Der Kern-Check nutzte `check_redis_url` mit **2 s** Socket-Connect/-Read-Timeout und **einem** PING-Versuch.
- Unter Docker/Last oder kurzen Netz-Glitches reicht das nicht; redis-py meldet dann u. a. `Timeout reading from socket` → `core_redis: false` trotz funktionsfähigem Redis.

## Fix (Implementierung)

| Bereich | Änderung |
|---------|----------|
| `shared_py.observability.health.check_redis_url` | Optional `retries` (Default `0` für alle bisherigen Aufrufer), Backoff, `health_check_interval=0`, `close()` im `finally`. |
| `GatewaySettings` | `GATEWAY_READINESS_REDIS_TIMEOUT_SEC` (Default **5.0**), `GATEWAY_READINESS_REDIS_RETRIES` (Default **2**). |
| `gateway_readiness_core` | Ruft `check_redis_url` mit Gateway-Settings auf. |
| Tests | `tests/unit/shared_py/test_check_redis_url_retries.py` (Retry nach Timeout, leere URL, ein Versuch bei sofortigem OK). |

## Testnachweis (lokal)

```text
python -m pytest tests/unit/shared_py/test_check_redis_url_retries.py tests/unit/api_gateway/test_gateway_ready_contract.py -q
```

Erwartung: alle grün.

## Laufzeit / Compose

Nach **Rebuild** des Images `api-gateway` (Code liegt im Repo, nicht nur Volume):

```text
docker compose build api-gateway
docker compose up -d api-gateway
```

## `rc:health` (Smoke)

```text
pnpm rc:health
```

Erwartung: Zeile `OK  gateway /ready` und Exit **0**.

Beispiel-Payload (Auszug): `checks.redis.ok: true`, `summary.core_redis: true`.

## Backout

- ENV: `GATEWAY_READINESS_REDIS_RETRIES=0` und ggf. `GATEWAY_READINESS_REDIS_TIMEOUT_SEC=2.0` — entspricht annähernd dem früheren Verhalten (ohne Retry-Logik im Gateway).
