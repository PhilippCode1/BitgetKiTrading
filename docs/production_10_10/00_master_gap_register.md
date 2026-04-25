# Master Gap-Register: Production-Readiness (Kanon + externe Luecken)

Diese Tabelle trennt **im Repo sichtbaren Stand** (Code, Tests, CI) von **externer Signoff-/Evidenz**, die in Git weder erzwungen noch ersetzt werden kann. Farblogik: siehe `readiness_evidence_schema.json` (Ampel).

| Kategorie            | Stichtag / Owner | Ziel-Mindest-EV fuer ECHTGELD-Strict (Tool) | Aktuell (typisch) | Bemerkung / harte Blocker aussenhalb Klon         |
| -------------------- | ---------------- | ------------------------------------------- | ----------------- | -------------------------------------------------- |
| CI / Branch-Protect  | (Infra)         | L3 CI in Git; L4+ GitHub-Policy **extern**  | L3+ Tool `check_github_branch_protection.py` | L4: API-Lauf/JSON+Report **oder** Org-Export; L5: Owner-Signoff auf Policy, nicht aus Klon; siehe `docs/ci_release_gates.md` |
| Disaster Recovery    | (SRE)           | L4 archivierter Report: Datum, `git_sha`, **Umgebung (name)**, RTO/RPO, **Status PASS** | L3 Skript+Tests+Runbook+`03_postgres_restore_drill.md` | **Grün** in der Ampel nur mit **einem** reellen Staging- (o.ä.) Durchlauf+Report; reines Doku-OK oder Lokalrechner ohne Staging-`PASS` = nicht grün. Tool: `tools/dr_postgres_restore_drill.py`.         |
| Shadow Burn-in      | (Trading/Ops)   | L4 archivierter Report: **PASS**, **report_sha256** (JSON), **git_sha**, Fenster, Umgebung | L3 `verify_shadow_burn_in.py`+Tests+`04_shadow_burn_in_certificate.md` | **Grün** nur mit echtem Staging-Lauf (72h+ empfohlen) und hinterlegter Datei+SHA; `NO_EVIDENCE` ersetzt kein Staging-`PASS`.   |
| Alert-Routing        | (SRE)           | L4: archivierter **Incident-/Testalarm-Drill** + Zustell-Nachweis  | L3: `verify_alert_routing.py`+`alertmanager.yml.example`+`05_*.md`  | **Grün** nur mit realem On-Call-/Staging-Nachweis, nicht mit Repo-Struktur allein; Pager/Slack live extern.  |
| Security-Audit      | (Security)      | L3: negative Auth/RBAC/RateLimit-Tests + Smoke; L4 externe Review/Pentest | L3: Unit-Suite (`tests/unit/api_gateway/*` inkl. `test_security_audit_suite.py`) + `tools/security_audit_smoke.py` | Voll gruen erst mit externem Pen-Test/Threat-Review-Bericht (Datum, Scope, Findings, Owner-Signoff) |
| Kunden-UI (Dashboard) | (Product)      | L3 CI Build+Jest+E2E fuer Portal; L4 Produktabnahme extern | L2-L3: Customer-Portal-Skeleton + BFF-Stub (`not_configured` moeglich) | Nur **teilweise gruen** ohne echte Commerce-/Billing-/Signal-Backendnachweise; Domain/TLS/Consent/Support-SLA ausserhalb Repo |
| Secrets / Vault     | (Infra)         | L4+ Rolling/Rotation-Probe                  | L3 `tools/inventory_secret_surfaces.py` + `tools/verify_production_secret_sources.py` + Doku; **L4+ nur mit echter Vault/KMS-Evidence/Rotation-Drill** | Volle gruene Ampel erst mit externem Store-Nachweis, nicht mit Template-PASS allein. |
| Live-Mirror-Gate   | (Trading)       | L3 Policy+Tests + Script `verify_live_mirror_gate.py`, L4 Staging-Drill | L3 (lokal): Gate-Matrix + Unit-Tests + Verifier-Script | L4 bleibt extern: echte Exchange-/Staging-Abnahme mit operatorischer Freigabe und archivierter Evidence |
| Performance / Alpha| (Quants)        | L3 Gates, L4 Staging-Metrikbericht         | L2–L3            | Kosten, Slippage, SLO-Realwerte                    |
| Compliance (Recht)  | (Legal)         | L5                                         | L1 Doku-Outline  | AGB, Risiko, Auftragsverarbeitung signiert         |
| Release-Evidence    | (RelEng)        | L3+ Release-Artefakte, L4 Archivlauf         | L3 in CI+Tools  | Dossier, Approvals, Staging-Abnahme-Links          |

Verknuepfte Doku: `../EXTERNAL_GO_LIVE_DEPENDENCIES.md`, `../LAUNCH_DOSSIER.md`, `../LaunchChecklist.md`.

Aktualisierungskette: aenderungen an Echtgeld-Mindestbarriere → dieses Register + ggf. `readiness_policy.json` (eingebettet in `tools/production_readiness_audit.py`).
