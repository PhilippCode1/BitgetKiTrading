# Reconcile-Truth-Drill (simulated)

## Szenario: exchange_order_missing
- Ergebnisstatus: warning
- Reconcile required: True
- Safety-Latch required: False
- Main-Console-Status: WARNUNG/OK
- Gruende: Lokale offene Order fehlt auf der Exchange.

## Szenario: local_order_missing
- Ergebnisstatus: warning
- Reconcile required: True
- Safety-Latch required: False
- Main-Console-Status: WARNUNG/OK
- Gruende: Exchange-Order fehlt lokal.

## Szenario: position_mismatch
- Ergebnisstatus: blocked
- Reconcile required: False
- Safety-Latch required: False
- Main-Console-Status: BLOCKIERT
- Gruende: Positionsabweichung zwischen lokal und Exchange erkannt.

## Szenario: stale_reconcile
- Ergebnisstatus: blocked
- Reconcile required: False
- Safety-Latch required: False
- Main-Console-Status: BLOCKIERT
- Gruende: Reconcile ist stale.

## Szenario: unknown_order_state
- Ergebnisstatus: blocked
- Reconcile required: False
- Safety-Latch required: False
- Main-Console-Status: BLOCKIERT
- Gruende: Unklarer Order-Status vorhanden.

## Szenario: safety_latch_required
- Ergebnisstatus: blocked
- Reconcile required: False
- Safety-Latch required: True
- Main-Console-Status: BLOCKIERT
- Gruende: Fill-Abweichung erkannt.
