# Bitget Demo Readiness

- Ergebnis: `PASS_WITH_WARNINGS`
- Modus: `demo-order-dry-run`
- Demo-Order ausgeführt: `false`
- Live-Trading-Freigabe: `NEIN`

## Checks
- `mode`: `demo-order-dry-run`
- `execution_mode`: `bitget_demo`
- `live_trade_enable`: `false`
- `demo_order_submit_enable`: `false`
- `bitget_demo_enabled`: `true`
- `demo_keys`: `ok`
- `live_keys_present`: `false`
- `paptrading_header`: `1`
- `demo_endpoint`: `ok`
- `server_time_http`: `200`
- `demo_position_mode`: `hedge`
- `demo_order_payload`: `{'symbol': 'BTCUSDT', 'productType': 'USDT-FUTURES', 'marginMode': 'isolated', 'marginCoin': 'USDT', 'size': '0.001', 'side': 'buy', 'orderType': 'market', 'clientOid': 'bgai-demo-1777210972', 'tradeSide': 'open'}`
- `demo_order_fields`: `clientOid,marginCoin,marginMode,orderType,productType,side,size,symbol,tradeSide`
- `demo_order_has_tradeside`: `true`
- `demo_order_has_reduceonly`: `false`
- `demo_order_payload_summary`: `symbol=BTCUSDT, productType=USDT-FUTURES, marginCoin=USDT, size=0.001, maxNotional=25.0`
- `demo_order_executed`: `false`

## Blocker
- keine

## Warnungen
- Demo- und Live-REST-Basis sind identisch; paptrading Header strikt pruefen.

## Env Snapshot (redacted)
```json
{
  "BITGET_API_BASE_URL": "https://api.bitget.com",
  "BITGET_API_KEY": "missing",
  "BITGET_API_PASSPHRASE": "missing",
  "BITGET_API_SECRET": "missing",
  "BITGET_DEMO_API_KEY": "set_redacted",
  "BITGET_DEMO_API_PASSPHRASE": "set_redacted",
  "BITGET_DEMO_API_SECRET": "set_redacted",
  "BITGET_DEMO_ENABLED": "true",
  "BITGET_DEMO_PAPTRADING_HEADER": "1",
  "BITGET_DEMO_REST_BASE_URL": "https://api.bitget.com",
  "DEMO_ORDER_SUBMIT_ENABLE": "false",
  "EXECUTION_MODE": "bitget_demo",
  "LIVE_TRADE_ENABLE": "false"
}
```
