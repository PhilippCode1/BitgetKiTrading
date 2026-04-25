# Bitget Demo Readiness

- Ergebnis: `FAIL`

## Checks
- `execution_mode`: `bitget_demo`
- `live_trade_enable`: `false`
- `bitget_demo_enabled`: `true`
- `demo_keys`: `missing`
- `demo_endpoint`: `ok`
- `server_time_http`: `skipped`

## Blocker
- Demo-Credentials fehlen (BITGET_DEMO_*).

## Warnungen
- Demo- und Live-REST-Basis sind identisch; paptrading Header strikt pruefen.

## Env Snapshot (redacted)
```json
{
  "BITGET_API_BASE_URL": "https://api.bitget.com",
  "BITGET_API_KEY": "missing",
  "BITGET_API_PASSPHRASE": "missing",
  "BITGET_API_SECRET": "missing",
  "BITGET_DEMO_API_KEY": "missing",
  "BITGET_DEMO_API_PASSPHRASE": "missing",
  "BITGET_DEMO_API_SECRET": "missing",
  "BITGET_DEMO_ENABLED": "true",
  "BITGET_DEMO_REST_BASE_URL": "https://api.bitget.com",
  "EXECUTION_MODE": "bitget_demo",
  "LIVE_TRADE_ENABLE": "false"
}
```
