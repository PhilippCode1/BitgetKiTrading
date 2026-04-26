# Bitget Readiness Report

- Datum/Zeit: `2026-04-26T09:02:59.386982+00:00`
- Git SHA: `339dd15`
- Modus: `public`
- ENV-Profil: `production`
- Status: `not_enough_evidence`
- Credential-Typ: `none`
- API-Version/Pfade: `/api/v2/public/time, /api/v2/spot/public/symbols, /api/v2/mix/market/contracts, /api/v2/spot/account/assets, /api/v2/mix/account/accounts`
- Public API Status: `ready`
- Private Read-only Status: `unavailable`
- Permission Status: `degraded`
- Instrument Universe Status: `ready`
- ProductType/MarginCoin Mapping: `ready`
- Rate Limit Status: `ready`
- Demo-Trade-Smoke Ack: `false`
- Demo-Trade-Smoke ausgefuehrt: `false`
- Live-Write erlaubt: `false`

## Blocker

## Warnings
- `private_runtime_not_checked`

## Redacted JSON
```json
{
  "api_version_paths": [
    "/api/v2/public/time",
    "/api/v2/spot/public/symbols",
    "/api/v2/mix/market/contracts",
    "/api/v2/spot/account/assets",
    "/api/v2/mix/account/accounts"
  ],
  "blockers": [],
  "checked_at": "2026-04-26T09:02:59.386982+00:00",
  "contract_version": "bitget-exchange-readiness-v1",
  "credential_summary": {
    "demo_key": "missing_or_placeholder",
    "demo_passphrase": "[REDACTED]",
    "demo_secret": "[REDACTED]",
    "live_key": "missing_or_placeholder",
    "live_passphrase": "[REDACTED]",
    "live_secret": "[REDACTED]"
  },
  "credential_type": "none",
  "demo_trade_smoke_executed": false,
  "demo_trade_smoke_guard_ack": false,
  "environment": "production",
  "git_sha": "339dd15",
  "instrument_universe_status": {
    "classification": "ok",
    "detail": "instrument universe response received",
    "http_status": 200,
    "status": "ready"
  },
  "live_write_allowed": false,
  "mode": "public",
  "permission_status": {
    "classification": null,
    "detail": "runtime permission evidence missing",
    "http_status": null,
    "status": "degraded"
  },
  "private_readonly_status": {
    "classification": null,
    "detail": "private read-only not executed",
    "http_status": null,
    "status": "unavailable"
  },
  "product_mapping_status": {
    "classification": null,
    "detail": "productType=USDT-FUTURES; marginCoin=USDT",
    "http_status": null,
    "status": "ready"
  },
  "public_api_status": {
    "classification": "ok",
    "detail": "server_time_offset_ms=739",
    "http_status": 200,
    "status": "ready"
  },
  "rate_limit_status": {
    "classification": null,
    "detail": "no rate limit observed",
    "http_status": null,
    "status": "ready"
  },
  "status": "not_enough_evidence",
  "warnings": [
    "private_runtime_not_checked"
  ]
}
```
