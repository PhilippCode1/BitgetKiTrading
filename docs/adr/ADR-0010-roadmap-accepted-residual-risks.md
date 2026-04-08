# ADR-0010: Accepted Residual Risks nach Roadmap-Stufen 1–10

**Status:** accepted  
**Datum:** 2026-04-01  
**Kontext:** Abschlussaudit der 10-Prompt-Roadmap (`docs/ROADMAP_10_10_CLOSEOUT.md`). Ziel ist ehrliche Abgrenzung gegenüber einer fiktiven „10/10 ohne jede offene Lücke“.

## Entscheidung

Folgende Punkte bleiben **bewusst akzeptiert** (kein Produktionsblocker im dokumentierten Produktziel: operator-gated Live):

1. **Exchange- und Netz-Chaos** ohne dedizierte Staging-Pipeline mit Freigaben und Credentials — nicht im CI reproduzierbar; Soak/Chaos manuell oder Job-Runner in Staging (`docs/TESTING_AND_EVIDENCE.md`).
2. **Multi-Asset-Breite** über die dokumentierte „eine Primärinstanz pro Stream“-Topologie hinaus — Operations- und Kapazitätsentscheid, nicht nur Code.
3. **Vollständige typisierte Abdeckung** aller Gateway-/Dashboard-Responses — iterativ; Kern über OpenAPI-Export + `check_contracts.py` abgesichert.

## Konsequenzen

- `FINAL_SCORECARD.md` darf **nicht** pauschal alle Zeilen auf **10** setzen, solange obige Reste offen kommuniziert werden.
- Neue Features, die diese Risiken erhöhen (z. B. weiteres Host-Publishing), müssen Truth-/Gap-Matrix und Runbooks anpassen.

## Verweise

- `docs/ROADMAP_10_10_CLOSEOUT.md`
- `docs/REPO_FREEZE_GAP_MATRIX.md`
- `docs/FINAL_SCORECARD.md`
