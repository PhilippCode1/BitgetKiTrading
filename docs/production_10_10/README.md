# Production 10/10 - Wahrheits- und Evidenz-Schicht

Dieser Ordner ist die kanonische Arbeitsgrundlage fuer Production-Readiness in
`bitget-btc-ai`. Er trennt strikt zwischen Repo-Nachweis und institutionellem
Echtgeld-Go-Live.

Eine Dokuzeile, die "10/10" sagt, darf niemals bedeuten, dass externe Beweise
wie Signoff, Penetrationstest, reale Exchange-Abnahme, Vault-Betrieb oder
On-Call-Kanal vorliegen, wenn diese Evidence fehlt.

## Verbindlichkeit

Fuer Codex und spaetere KI-Agenten gelten in dieser Reihenfolge:

1. `AGENTS.md` im Repo-Root
2. `docs/production_10_10/codex_work_protocol.md`
3. `docs/production_10_10/no_go_rules.md`
4. `docs/production_10_10/10_10_definition.md`
5. `docs/production_10_10/evidence_matrix.md`

Bei Konflikten gilt die strengere, sicherere und fail-closed Auslegung.

## Scope: Was beweist das Repo?

- Beweisbar im Klon (L1-L3): Quellcode, `pytest`, Jest, E2E, `tools/*`-Gates
  und CI-Definitionen.
- Nur mit Zusatzartefakten (L4): Staging-Reports, archivierte Burn-in-,
  Restore-, Alert- oder Drill-Reports unter `docs/release_evidence/`.
- Ausschliesslich extern (L5): Legal-/Management-Signoff, reale Bitget-Keys,
  Branch-Protection in GitHub, TLS/DNS, Vault/KMS, reale On-Call-Zustellung,
  Penetrationstest und Kunden-/Commercial-Freigaben.

## Einstiegsdateien

| Datei                                                              | Zweck                                                                                   |
| ------------------------------------------------------------------ | --------------------------------------------------------------------------------------- |
| [10_10_definition.md](./10_10_definition.md)                       | Harte Definition der 20 Production-Readiness-Kategorien.                                |
| [evidence_matrix.md](./evidence_matrix.md)                         | Konservative Matrix aus Bereich, Ziel, Nachweis, Status, Blocker und naechstem Schritt. |
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
python tools/release_sanity_checks.py
python tools/check_release_approval_gates.py
pnpm format:check
```

Zusaetzlich je nach Bereich:

```bash
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
