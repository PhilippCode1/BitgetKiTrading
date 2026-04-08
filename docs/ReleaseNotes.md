# Release Notes

## v1.2.0 (Release-Bereinigung — 2026-03-30)

### Highlights

- `docs/SYSTEM_AUDIT_MASTER.md` auf **Verweisdokument** reduziert; historische,
  mit Compose **widerspruechliche** Audit-Phasen entfernt (`docs/RELEASE_CLEANUP_REPORT.md`).
- README / Deploy / Dev-Workflow / Gap-Matrix: **Dashboard-Produktion = Next standalone +
  `node build/standalone/...`**, nicht `next start`.
- Lokaler Build-Ballast `apps/dashboard/build-cursor/` ignoriert und aus Sanity-Scans
  ausgeschlossen; `.prettierignore` fuer Artefakt-Pfade.
- Dashboard-Jest-Dev-Dependencies **exakt gepinnt** (ohne `^`).
- `infra/service-manifest.yaml`: `release_auditability`; neu: `docs/REPO_SBOM_AND_RELEASE_METADATA.md`.

### Grenzen (unveraendert)

- Paper-Broker Fixture-Fallback, Replay-Determinismus, Grafana-Platzhalter — siehe
  `docs/REPO_FREEZE_GAP_MATRIX.md` und `docs/FINAL_READINESS_REPORT.md`.

## v1.0.0 (Produktionsreife V1 — Prompt 30)

### Highlights

- Zentrale **ENV-Validierung** mit pydantic (`config/settings.py`, `config/gateway_settings.py`).
- **Strukturiertes Logging** (JSON oder plain) mit Feld `service` und steuerbarem `LOG_LEVEL` / `LOG_FORMAT`.
- **Secret-Management-Hinweise**: Produktion warnt, wenn `VAULT_MODE=false`/`none` (keine Klartext-Secrets im Repo).
- **Start-/Health-/Deploy-Skripte** unter `scripts/`.
- Dokumentation: `docs/Deploy.md`, `docs/LaunchChecklist.md`, README-Abschnitt Production-Quickstart.

### Breaking Changes

- Python-Services erwarten bei lokalem Start aus dem Quellbaum den **Repo-Root** auf `PYTHONPATH` (Docker setzt `/app`). API-Gateway und ausgewaehlte Services rufen `bootstrap_service()` beim Start auf.

### Service-Versionen

- Monorepo-Metapaket: Workspace 0.0.0; Microservices unabhaengig versioniert in jeweiligen `pyproject.toml` (0.1.0).

### Bekannte Einschraenkungen

- Vault/KMS: nur Dokumentation und ENV-Schalter; keine eingebettete Vault-Client-Implementierung.
- Dashboard: strukturierte Server-Logs optional via `winston` (`apps/dashboard/src/lib/server-logger.ts`).

## v1.1.0 (Betrieb, Forensik und Launch-Vertrag)

### Highlights

- Shadow-Burn-in, enge Echtgeld-Mirror-Stufe und Ramp-Strategie als kanonischer Betriebsvertrag: `docs/shadow_burn_in_ramp.md`
- End-to-End-Trade-Forensik ueber Dashboard und Gateway (`/live-broker/forensic/[id]`)
- Operator-SOPs, Onboarding und kanonische Statussprache:
  - `docs/operator_sops.md`
  - `docs/operator_onboarding_checklist.md`
  - `docs/operator_status_language.md`
- Strengere Release-/Artefakt-Hygiene:
  - `constraints-runtime.txt`
  - Standalone-Dashboard-Build
  - erweiterte `release_sanity_checks.py`

### Wichtige Grenzen

- Vollautonomer Echtgeldbetrieb bleibt **nicht** freigegeben.
- Die erste reale Echtgeldstufe bleibt operator-gated mirror mit konservativem Hebel.
- Ehrlicher Abschlussstand und verbleibende interne/externe Blocker: `docs/FINAL_READINESS_REPORT.md`
