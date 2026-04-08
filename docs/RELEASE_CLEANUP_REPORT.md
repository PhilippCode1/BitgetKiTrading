# Release-Bereinigung — Cleanup-Report

**Datum:** 2026-03-30  
**Ziel:** Kompromisslose Angleichung von Doku, Artefaktgrenzen und Dependency-Pins an den **Ist-Stand** (keine schoeneren Claims als der Code).

## Entfernte oder entschaerfte Altlasten

| Element                                                  | Massnahme                                                                                                                                                                                         |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/SYSTEM_AUDIT_MASTER.md` (Phasen 1–10, ~360 Zeilen) | **Entfernt.** Inhalt behauptete u. a. fehlende Pipeline-Services in Compose — **widersprach** `docker-compose.yml`. Ersatz: kurzes **Verweisdokument** auf Truth-/Gap-Matrizen und SBOM-Hinweise. |
| `apps/dashboard/build-cursor/`                           | **Verzeichnis geloescht** (lokaler Next-/Tool-Output, kein Deliverable). **Nicht** wieder einchecken.                                                                                             |
| Widerspruechliche „`next start` in Prod“-Formulierungen  | In **README**, **Deploy.md**, **dev-workflow.md**, **REPO_FREEZE_GAP_MATRIX** auf **Standalone-Start** vereinheitlicht.                                                                           |

## Dependency- / Reproduzierbarkeit

| Bereich                     | Aenderung                                                                                                                                                                |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Dashboard `devDependencies` | Caret entfernt: `@testing-library/jest-dom` **6.9.1**, `@testing-library/react` **16.3.2**, `jest-environment-jsdom` **30.3.0** (entspricht bisherigem Lock).            |
| Python                      | Keine Aenderung an `constraints-runtime.txt` / `requirements-dev.txt` (bereits `==`); Klarstellung in Truth-/Gap-Matrix: **Release** nutzt `-c constraints-runtime.txt`. |
| Root `package.json`         | Bereits gepinnt (`prettier`, `turbo`, `packageManager`).                                                                                                                 |

## Packaging / `.gitignore` / Sanity-Checks

- `.gitignore`: `apps/dashboard/build-cursor/`
- `.dockerignore`: `apps/dashboard/build-cursor` (+ `/**`)
- `.prettierignore`: Build-/Cache-Pfade inkl. `build-cursor`
- `tools/release_sanity_checks.py`: `SKIP_DIRS` um **`build-cursor`** ergaenzt
- `infra/service-manifest.yaml`: Abschnitt **`release_auditability`** (Lockfiles + SBOM-Verweis)

## Neue kanonische Doku

- `docs/REPO_SBOM_AND_RELEASE_METADATA.md` — SBOM-Erzeugung (optional, CI-Artefakt), Lockfile-Kanon
- Dieses Dokument — Ballast- und Pin-Log

## Aktualisierte Querschnitts-Doku

- `docs/REPO_TRUTH_MATRIX.md` (Stand, Migrationen 65, Audit-Zeile)
- `docs/REPO_FREEZE_GAP_MATRIX.md` (Dashboard-Prod-Start, Tests/Coverage-Zeile, Audit-Block, Doku-Zaehlung)
- `docs/FINAL_READINESS_REPORT.md` (Coverage-/Test-ENV ehrlicher; Audit-Zeile)
- `docs/LAUNCH_DOSSIER.md` (SBOM-Zeile im Index)
- `docs/ReleaseNotes.md` — v1.2.0 Eintrag

## Bewusst nicht behauptet

- Kein automatisch eingechecktes CycloneDX-JSON (Drift-Risiko); stattdessen **Hinweise** und Manifest-Verweise.
- Service-`pyproject.toml` bleiben mit **Ranges** fuer lokale editable Installs; **Images** bleiben ueber Constraints verbindlich.
