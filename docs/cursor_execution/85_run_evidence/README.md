# Run-85 Evidenz (P85)

Dieser Ordner wird von `python tools/build_run85_dossier.py` befüllt.

| Datei | Quelle |
|--------|--------|
| `iron_curtain.log` | Ausgabe von `pnpm release:gate:full` (P84) |
| `shadow_burn_in.md` | `python scripts/verify_shadow_burn_in.py --readiness-out ...` |
| `reasoning_accuracy.json` | `python scripts/ai_reasoning_accuracy_report.py --json-out ...` |
| `*.png` | `pnpm exec playwright test e2e/tests/run85_dossier_evidence.spec.ts` |
| `dossier_meta.json` | Metadaten des letzten Dossier-Laufs |
| `collect_*` | Optional: Kopien aus `collect_release_evidence.ps1` mit `--ingest` |

PNG-Dateien sind laufzeitabhängig und werden typischerweise nicht versioniert.
