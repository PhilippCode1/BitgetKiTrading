# Demo Trading Evidence Report

- Ergebnis: `FAILED`
- Demo verifiziert: `false`
- Echtes Live-Trading erlaubt: `false`
- Hinweis: Demo-Evidence ersetzt keine private_live_allowed-Freigabe.

## Checks
- `readonly_result`: `FAIL`
- `private_readonly_result`: `not_run`
- `order_dry_run_result`: `not_run`
- `demo_order_smoke_result`: `not_run`
- `demo_order_executed`: `false`
- `live_trading_allowed`: `false`
- `private_live_allowed`: `false`

## Blocker
- Demo-Credentials fehlen (BITGET_DEMO_*).

## Warnungen
- Demo- und Live-REST-Basis sind identisch; paptrading Header strikt pruefen.

## Statuslogik
- `DEMO_READY`: Demo-ENV/Readiness ist technisch brauchbar, aber noch keine echte Demo-Order bewiesen.
- `DEMO_VERIFIED`: Private Demo-Read-only und bewusster Demo-Order-Smoke wurden erfolgreich ausgeführt.
- `private_live_allowed` bleibt immer `false`, bis separate Live-/Owner-/Shadow-/Restore-/Alert-Evidence vorhanden ist.
