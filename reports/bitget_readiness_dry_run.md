# Bitget Readiness Report

- Datum/Zeit: `2026-04-25T23:27:34.764600+00:00`
- Git SHA: `84d7b66`
- Modus: `dry-run`
- ENV-Profil: `production`
- Credential-Typ: `none`
- API-Version/Pfade: `/api/v2/public/time, /api/v2/spot/public/symbols, /api/v2/mix/market/contracts, /api/v2/spot/account/assets, /api/v2/mix/account/accounts`
- Public API Status: `unavailable`
- Private Read-only Status: `unavailable`
- Permission Status: `degraded`
- Instrument Universe Status: `unavailable`
- ProductType/MarginCoin Mapping: `ready`
- Rate Limit Status: `ready`
- Ergebnis: `PASS_WITH_WARNINGS`
- Live-Write erlaubt: `false`

## Blocker

## Warnings
- `api_version_v2_paths_documented_v1_usage_is_risk`
- `dry_run_no_public_network_evidence`
- `dry_run_no_private_auth_evidence`
- `dry_run_no_instrument_universe_evidence`
- `permission_evidence_missing_live_write_blocked`

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
  "env_profile": "production",
  "generated_at": "2026-04-25T23:27:34.764600+00:00",
  "git_sha": "84d7b66",
  "instrument_universe_status": {
    "classification": null,
    "detail": "dry-run: instrument discovery not executed",
    "http_status": null,
    "status": "unavailable"
  },
  "live_write_allowed": false,
  "mode": "dry-run",
  "permission_status": {
    "classification": null,
    "detail": "permission evidence missing; live write remains blocked",
    "http_status": null,
    "status": "degraded"
  },
  "private_readonly_status": {
    "classification": null,
    "detail": "dry-run: private read-only not executed",
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
    "classification": null,
    "detail": "dry-run: no network calls",
    "http_status": null,
    "status": "unavailable"
  },
  "rate_limit_status": {
    "classification": null,
    "detail": "no rate limit observed in dry-run",
    "http_status": null,
    "status": "ready"
  },
  "result": "PASS_WITH_WARNINGS",
  "warnings": [
    "api_version_v2_paths_documented_v1_usage_is_risk",
    "dry_run_no_public_network_evidence",
    "dry_run_no_private_auth_evidence",
    "dry_run_no_instrument_universe_evidence",
    "permission_evidence_missing_live_write_blocked"
  ]
}
```
