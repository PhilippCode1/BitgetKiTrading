# Reconcile und Exchange-Truth pro Asset

## Lokale Wahrheit vs Exchange-Wahrheit

Live-Betrieb ist nur sicher, wenn lokale Orders/Fills/Positionen mit der
Exchange-Wahrheit je Asset abgeglichen werden.

## Reconcile-Status

- ok
- warning
- stale
- drift_detected
- exchange_unreachable
- auth_failed
- rate_limited
- unknown_order_state
- local_order_missing
- exchange_order_missing
- position_mismatch
- fill_mismatch
- safety_latch_required
- blocked

## Drift-Arten

- local/exchange order missing
- position mismatch
- fill mismatch
- stale reconcile snapshot
- unknown order state

## Harte Blockregeln

- stale / exchange_unreachable / auth_failed / unknown_order_state blockieren.
- position_mismatch blockiert.
- fill_mismatch blockiert oder erzwingt Safety-Latch.
- order_missing-Faelle erzeugen Reconcile-Required.
- aktiver Safety-Latch blockiert normale Opening-Orders.
- Reduce-only/Emergency laufen als separater Safety-Pfad.

## Main-Console-Anzeige

- globaler Reconcile-Status
- Status pro Asset
- offene Drift-Faelle
- Safety-Latch-Status
- letzte erfolgreiche Reconcile-Zeit
- deutscher Blockgrund

## Audit

Reconcile-Entscheidungen muessen mit Status, Gruenden und per-Asset-Zustand
auditierbar sein, ohne Secrets zu loggen.

## Referenzen

- `services/live-broker/README.md`
- `docs/production_10_10/live_broker_multi_asset_preflight.md`

## No-Go

Bei Reconcile-Unklarheit darf kein neues Live-Opening starten.
