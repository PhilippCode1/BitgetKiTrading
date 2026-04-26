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

## Externer Reconcile-/Idempotency-Contract

Der simulierte Drill ist Code-Evidence, aber keine Live-Freigabe. Fuer private
Live-Evidence muss ein echter Staging-/Shadow-Drill als secret-freies JSON gegen
den Contract geprueft werden:

```bash
python scripts/reconcile_truth_drill.py \
  --evidence-json docs/production_10_10/reconcile_idempotency_evidence.template.json \
  --strict \
  --output-md reports/reconcile_idempotency_evidence.md \
  --output-json reports/reconcile_idempotency_evidence.json
```

Das Repo-Template bleibt absichtlich `FAIL`, bis echte Evidence vorliegt. Fuer
Live muss mindestens belegt sein:

- Drill-Start/-Ende, Git-SHA, Operator und Evidence-Referenz
- Exchange-Truth-Quelle dokumentiert
- `reconcile_status=ok`
- frischer Reconcile-Snapshot
- Reconcile pro Asset `ok`
- keine offene Drift, unknown order states, Position-/Fill-Mismatches oder
  fehlende Exchange-Acks
- Retry ohne Reconcile blockiert
- Duplicate `client_oid` blockiert
- Idempotency-Key ist Pflicht
- Timeout fuehrt zu `unknown_submit_state`
- Unknown submit state blockiert neue Openings
- DB-Fehler nach Submit erzwingt Reconcile
- ungeloeste Duplicate-Recovery armt Safety-Latch
- Audit-Trail, Alert-Zustellung und Main-Console-Reconcile-State verifiziert
- `live_write_allowed_during_drill=false`
- `real_exchange_order_sent=false`
- Owner-Signoff separat vorhanden

Felder mit Secret-Bezug wie `database_url`, `dsn`, `password`, `secret`,
`token`, `api_key`, `private_key` oder `authorization` duerfen keine echten Werte
enthalten.

## Referenzen

- `services/live-broker/README.md`
- `docs/production_10_10/live_broker_multi_asset_preflight.md`

## No-Go

Bei Reconcile-Unklarheit darf kein neues Live-Opening starten.
