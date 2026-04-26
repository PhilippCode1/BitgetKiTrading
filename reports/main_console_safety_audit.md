# Main Console Safety / Audit Evidence Report

Status: synthetischer Nachweis fuer ehrliche Operator-Sicht, Live-NO-GO und Audit/Forensics.

## Summary

- Datum/Zeit: `2026-04-25T22:59:46.575808+00:00`
- Git SHA: `84d7b66`
- Private Live: `NO_GO`
- Full Autonomous Live: `NO_GO`
- Szenarien: `5`
- Audit valide: `5`
- Secret-safe: `True`
- Fehlende sichtbare Gates: `0`
- Blocking-Failures: `0`

## Szenarien

| Szenario | Private Live | Echte Orders moeglich | Blockgruende | Deutscher Operator-Text | Audit valide |
| --- | --- | --- | --- | --- | --- |
| `reconcile_unknown` | `NO_GO` | `False` | `reconcile_status_blocks_live` | Reconcile ist unklar oder fehlerhaft; Live bleibt verboten. | `True` |
| `exchange_truth_missing` | `NO_GO` | `False` | `exchange_truth_blocks_live` | Exchange-Truth fehlt oder ist stale; Live bleibt verboten. | `True` |
| `kill_switch_active` | `NO_GO` | `False` | `kill_switch_blocks_live` | Kill-Switch ist aktiv; echte Orders sind gesperrt. | `True` |
| `safety_latch_active` | `NO_GO` | `False` | `safety_latch_blocks_live` | Safety-Latch ist aktiv; Submit/Replace bleibt gesperrt. | `True` |
| `backend_unavailable` | `NO_GO` | `False` | `backend_unavailable_blocks_live` | Backend ist nicht verbunden; Safety-State ist nicht belastbar und Live bleibt verboten. | `True` |

## Einordnung

- Synthetische Repo-Evidence ohne echte Orders und ohne Secrets.
- Main Console muss Live-Verbote, blockierende Gates und deutsche Forensics-Texte sichtbar machen.
- Dieser Report ersetzt keine externe Shadow-, Bitget-, Alert- oder Owner-Signoff-Evidence.
