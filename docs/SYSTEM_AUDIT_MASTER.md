# System-Audit — Verweisdokument (kanonisch)

**Stand:** 2026-03-30 (Release-Bereinigung)

## Rolle

Diese Datei ist **kein** eigenstaendiger Audit-Bericht mehr. Sie verweist auf die
**kanonischen** Ist- und Lueckenbeschreibungen des Repos. Aeltere, mehrseitige
Phasen-Texter (P1–P10) wurden entfernt, weil sie dem **aktuellen**
`docker-compose.yml` und der Pipeline **widersprachen** (z. B. fehlende
Pipeline-Services — historisch falsch).

## Kanonische Quellen (in dieser Reihenfolge lesen)

1. `docs/REPO_TRUTH_MATRIX.md` - Repo-Wahrheit, Topologie, Risiken
2. `docs/REPO_FREEZE_GAP_MATRIX.md` - Gap-/Artefakt-Matrix
3. `docs/FINAL_READINESS_REPORT.md` - ehrlicher Freigabe- und Reststand
4. `docs/LAUNCH_DOSSIER.md` - Freigabeleiter, Cutover, Blocker
5. `docs/Deploy.md` - ENV, Profile, Compose-Bezug
6. `docs/adr/ADR-0001-bitget-market-universe-platform.md` - Zielarchitektur

## Auditierbarkeit / Abhaengigkeiten

- **Python-Laufzeit (gepinnt):** `constraints-runtime.txt` — in Service-Dockerfiles
  und CI wie dokumentiert mit `pip install -c constraints-runtime.txt` zu verwenden.
- **Python-Dev/CI:** `requirements-dev.txt` (alle Zeilen mit `==`).
- **Node:** Root-`pnpm-lock.yaml` — Release mit `pnpm install --frozen-lockfile`.
- **Formale SBOM (CycloneDX/SPDX):** nicht fest im Repo eingecheckt; Hinweise:
  `docs/REPO_SBOM_AND_RELEASE_METADATA.md`, `infra/service-manifest.yaml` →
  `release_auditability`.

## Regel bei Widerspruch

Gilt **Code + Compose + ENV-Validatoren + CI-Workflow** vor alter Markdown-Prosa.
