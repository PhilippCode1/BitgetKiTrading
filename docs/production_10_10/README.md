# Production 10/10 - Wahrheits- und Evidenz-Schicht

Dieser Ordner ist die kanonische Arbeitsgrundlage fuer Production-Readiness in
`bitget-btc-ai`. Er trennt strikt zwischen Repo-Nachweis und institutionellem
Echtgeld-Go-Live. Ab jetzt ist auch verbindlich: `bitget-btc-ai` ist eine
private deutsche Main-Console-Multi-Asset-Anwendung fuer Philipp Crljic, nicht
ein Verkaufs-, Billing-, Customer- oder Multi-Tenant-Produkt.

Diese Festlegung ist die bindende Grundlage fuer alle folgenden Cursor-Prompts.

Eine Dokuzeile, die "10/10" sagt, darf niemals bedeuten, dass externe Beweise
wie Signoff, Penetrationstest, reale Exchange-Abnahme, Vault-Betrieb oder
On-Call-Kanal vorliegen, wenn diese Evidence fehlt.

## Verbindlichkeit

Fuer Codex und spaetere KI-Agenten gelten in dieser Reihenfolge:

1. `AGENTS.md` im Repo-Root
2. `docs/production_10_10/private_owner_scope.md`
3. `docs/production_10_10/main_console_product_direction.md`
4. `docs/production_10_10/cursor_work_protocol.md`
5. `docs/production_10_10/codex_work_protocol.md`
6. `docs/production_10_10/no_go_rules.md`
7. `docs/production_10_10/10_10_definition.md`
8. `docs/production_10_10/evidence_matrix.yaml`
9. `docs/production_10_10/evidence_matrix.md`

Bei Konflikten gilt die strengere, sicherere und fail-closed Auslegung.

## Scope: Was beweist das Repo?

- Beweisbar im Klon (L1-L3): Quellcode, `pytest`, Jest, E2E, `tools/*`-Gates
  und CI-Definitionen.
- Nur mit Zusatzartefakten (L4): Staging-Reports, archivierte Burn-in-,
  Restore-, Alert- oder Drill-Reports unter `docs/release_evidence/`.
- Ausschliesslich extern (L5): Legal-/Owner-Signoff, reale Bitget-Keys,
  Branch-Protection in GitHub, TLS/DNS, Vault/KMS, reale On-Call-Zustellung,
  Penetrationstest und reale Betreiberfreigaben durch Philipp.

## Einstiegsdateien

| Datei                                                              | Zweck                                                                                   |
| ------------------------------------------------------------------ | --------------------------------------------------------------------------------------- |
| [10_10_definition.md](./10_10_definition.md)                       | Harte Definition der 20 Production-Readiness-Kategorien.                                |
| [evidence_matrix.yaml](./evidence_matrix.yaml)                     | Maschinenlesbare 30-Kategorien-Evidence-Matrix fuer Private Owner, Main Console und Live-Blocker. |
| [evidence_matrix.md](./evidence_matrix.md)                         | Menschenlesbare Sicht auf die YAML-Matrix und ihre Pflichtkategorien.                   |
| [evidence_status_report.md](./evidence_status_report.md)           | Generierter Statusbericht aus `tools/check_10_10_evidence.py --write-report`.          |
| [private_owner_scope.md](./private_owner_scope.md)                 | Verbindlicher Scope: Philipp als einziger Nutzer, keine Kunden, kein Billing.           |
| [main_console_product_direction.md](./main_console_product_direction.md) | Deutsche Main Console als zentrale Oberflaeche und Konsolidierungsziel.                 |
| [cursor_work_protocol.md](./cursor_work_protocol.md)               | Cursor-Arbeitsprotokoll fuer private Main-Console-Ausrichtung.                         |
| [codex_work_protocol.md](./codex_work_protocol.md)                 | Arbeitsprotokoll fuer Lesen, Planen, Aendern, Testen, Dokumentieren und Evidence.       |
| [no_go_rules.md](./no_go_rules.md)                                 | Harte Echtgeld-Blocker, die nicht ignoriert werden duerfen.                             |
| [00_master_gap_register.md](./00_master_gap_register.md)           | Bestehendes Gap-Register fuer externe Luecken und Mindestevidenz.                       |
| [readiness_evidence_schema.json](./readiness_evidence_schema.json) | Definitionen L0-L5 und Ampellogik.                                                      |
| [evidence_registry.md](./evidence_registry.md)                     | Registry fuer neue Evidence-Referenzen; ersetzt keine L4/L5-Evidence.                   |

## Statussprache

Nur diese Statuswerte sind erlaubt:

- `missing`
- `partial`
- `implemented`
- `verified`
- `external_required`

"10/10 erreicht" ist verboten, solange Evidence fehlt.

## Mindestbefehle fuer Doku-/Readiness-Aenderungen

```bash
python tools/check_10_10_evidence.py
python tools/release_sanity_checks.py
python tools/check_release_approval_gates.py
pnpm format:check
```

Zusaetzlich je nach Bereich:

```bash
python tools/check_10_10_evidence.py --strict
python tools/check_10_10_evidence.py --json
python tools/check_10_10_evidence.py --write-report docs/production_10_10/evidence_status_report.md
python tools/production_readiness_audit.py
python tools/production_readiness_audit.py --strict
python tools/inventory_secret_surfaces.py
python tools/verify_production_secret_sources.py
python tools/verify_alert_routing.py
python tools/validate_env_profile.py --env-file .env.production --profile production
```

## Ampel

- Gruen oder `verified`: Repo-pruefbare Evidence ist ausgefuehrt und bestanden,
  ohne externe Signoffs vorzutaeuschen.
- Gelb oder `partial`/`implemented`: Code, Tests oder Doku existieren, aber
  Evidence ist unvollstaendig.
- Rot oder `missing`: Nachweis fehlt oder No-Go-Regel ist offen.
- `external_required`: Repo kann die Anforderung vorbereiten, aber nicht allein
  beweisen.

## Grundsatz

Bei Unsicherheit blockiert das System. Fail-closed ist wichtiger als Komfort,
Demo-Faehigkeit oder schnelle Freigabe.

Ergaenzende Root-Hinweise:
[README.md](../../README.md),
[docs/FINAL_SCORECARD.md](../FINAL_SCORECARD.md),
[docs/EXTERNAL_GO_LIVE_DEPENDENCIES.md](../EXTERNAL_GO_LIVE_DEPENDENCIES.md).
