# Order-Lifecycle, Exit und Emergency Safety

## Order-Lifecycle

Von `candidate` bis `closed` gilt: jede State-Aenderung ist auditierbar und
fail-closed abgesichert.

## Idempotency und Unknown Submit State

- Kein Submit ohne `execution_id`.
- Kein Submit ohne Idempotency-Key oder Client-Order-ID.
- Timeout nach Submit => `unknown_submit_state`.
- `unknown_submit_state` blockiert neue Opening-Orders im Kontext.
- Retry ohne Reconcile ist verboten.
- Duplicate Client-Order-ID blockiert.
- DB-Failure nach Exchange-Submit => `reconcile_required`.

## Cancel/Replace

Cancel/Replace darf keine Duplikatorder erzeugen und muss den lokalen/exchange
State konsistent halten.

## Exit und Reduce-only

- Exit-Orders duerfen Position nicht ueberschreiten.
- Futures-Closing erzwingt `reduce_only`.
- TP-Splits duerfen kumuliert 100 Prozent nicht ueberschreiten.
- Precision/Tick/Step muessen passen.

## Emergency Flatten

- Darf keine neue Position eroeffnen.
- braucht Owner-Kontext oder harten Safety-Grund.
- Kill-Switch/Safety-Latch-Pfade bleiben separat sicher.

## Main-Console Anzeige

- Order-State
- Exchange-State
- Unknown/Reconcile-Required
- Exit-/Reduce-only-/Emergency-Status
- Blockgruende
- letzte Aktion

## Referenzen

- `services/live-broker/README.md`
- `docs/production_10_10/live_broker_multi_asset_preflight.md`

## No-Go

Unknown submit state, Duplicate-Order oder unsicherer Exit blockieren Live.
