# Audit, Forensik und Replay fuer die private Hauptkonsole

## Zielbild

Philipp muss jede kritische Entscheidung der privaten Trading-Anwendung
nachvollziehen koennen: Asset-Blockade, `do_not_trade`, Live-Block,
Asset-Quarantaene, Reconcile-Drift, Safety-Latch, Kill-Switch und
Bitget-Readiness.

Logs allein reichen nicht. Jede Entscheidung braucht einen auditierbaren
Contract mit Asset-, Risk-, Datenqualitaets-, Exchange- und Reconcile-Kontext.

## Pflichtfelder pro Audit-Event

- `event_id`
- `event_type`
- `timestamp`
- `git_sha` oder Build-Version, falls verfuegbar
- `service`
- `asset_symbol`
- `market_family`
- `product_type`
- `margin_coin`
- `decision_type`
- `decision`
- `reason_codes`
- `reason_text_de`
- `risk_tier`
- `liquidity_tier`
- `data_quality_status`
- `exchange_truth_status`
- `reconcile_status`
- `operator_context` (`philipp`, `owner`, `system`)
- `trace_id`
- `correlation_id`
- `no_secrets_confirmed`

Der technische Contract liegt in `shared/python/src/shared_py/audit_contracts.py`.

## Secret-Schutz

Audit-Events duerfen keine Secrets enthalten. Felder mit API-Key, Secret,
Passphrase, JWT, Authorization, Password oder Token werden redacted. Wenn ein
Payload unredactete Secret-Marker enthaelt, ist das Event ungueltig.

## Forensik-Ansichten in der Hauptkonsole

Die Forensik-Ansicht der Main Console zeigt spaeter mindestens:

- letzte blockierte Live-Entscheidungen
- letzte `do_not_trade`-Entscheidungen
- letzte Asset-Quarantaenegruende
- letzte Reconcile-Drifts
- letzte Safety-Latch-/Kill-Switch-Ereignisse
- letzte Bitget-Readiness-Pruefungen
- deutsche Zusammenfassung pro Ereignis

Diese Ansicht ist private Owner-Only und kein Customer-/Billing-/SaaS-Flow.

## Replay-Zusammenfassung

`shared/python/src/shared_py/replay_summary.py` bewertet, ob ein Replay
ausreichend ist. Fehlende Schritte werden nicht verschwiegen.

Pflichtschritte fuer ausreichendes Replay:

- Signal-Schritt
- Risk-Schritt mit `reason_codes`
- Exchange-Schritt mit `exchange_truth_status`

Fehlende Signal-/Risk-/Exchange-Schritte fuehren zu `replay_sufficient=false`.
LLM-Erklaerungen duerfen die Forensik ergaenzen, ersetzen aber nie die
Audit-Wahrheit.

## Harte Regeln

- Live-relevante Entscheidung ohne Asset-Kontext ist unvollstaendig.
- Order-relevante Entscheidung ohne Exchange-/Reconcile-Kontext ist unvollstaendig.
- Risk-Entscheidung ohne Reason Codes ist unvollstaendig.
- Replay-Luecken muessen sichtbar bleiben.
- Forensik-Texte fuer die Hauptkonsole sind deutsch.

## Tests

```bash
python tools/check_private_audit_forensics.py --strict
pytest tests/tools/test_check_private_audit_forensics.py -q
pytest tests/security/test_private_audit_forensics_contracts.py -q
python tools/release_sanity_checks.py
```

## Offener Anschluss

Die Contracts sind als sichere Grundlage implementiert. Der spaetere
End-to-End-Anschluss muss echte Signal-, Risk-, Exchange-, Reconcile- und
Operator-Daten in diese Contracts schreiben und in der Hauptkonsole anzeigen.
