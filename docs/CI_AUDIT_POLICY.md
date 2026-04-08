# CI: Supply-Chain & Audit-Policy

## Was die Pipeline erzwingt

- **pnpm:** `pnpm audit --audit-level=high` im Dashboard-Job — Findings **High** oder **Critical** im Lockfile brechen den Build. Ausnahmen nur per Dependency-Update oder dokumentiertem `pnpm.overrides` (siehe unten).
- **Python (pip):** `tools/pip_audit_supply_chain_gate.py` nach Install der Dev-Abhängigkeiten:
  - führt `pip-audit` mit `-r requirements-dev.txt` und `-r constraints-runtime.txt` aus,
  - klassifiziert jede Meldung über **OSV** (GitHub-Label HIGH/CRITICAL oder **CVSS-3.1-Base ≥ 7.0**),
  - **CI rot**, wenn ein solches Finding nicht in [`tools/pip_audit_allowlist.txt`](../tools/pip_audit_allowlist.txt) steht.
  - Zusätzlich: Paket `cvss` (nur für diesen Schritt in CI installiert) zur Base-Score-Berechnung.
- **Coverage:** `tools/check_coverage_gates.py` (wie bisher).
- **ENV-Profile:** `tools/validate_env_profile.py` mit substituiertem `.env.local.example`.
- **Weitere Gates:** `tools/release_sanity_checks.py`, Compose-Config + `scripts/healthcheck.sh` im Job `compose_healthcheck`.

## Dokumentierte Ausnahmen (Allowlist)

Datei: **`tools/pip_audit_allowlist.txt`** — eine Vulnerability-ID pro Zeile (`GHSA-*`, `CVE-*`, …), Kommentare mit `#`.

Aktuell:

| ID                    | Begründung                                                                                                                                                                                                   |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `GHSA-3936-cmfr-pm3m` | Black &lt; 26.3.1: betrifft nur die CLI-Option `--python-cell-magics` mit untrusted Input. Im Repo nur Dev/CI ohne solche Nutzung. Upgrade auf Black 26.x erzwingt großen Reformat — geplant als eigener PR. |

**PyJWT** wurde auf **2.12.1** angehoben (Fix für GHSA-752w-5fwx-jx9f), statt Allowlist.

**npm/pnpm:** `handlebars>=4.7.9` als Root-`pnpm.overrides` (transitiv über `ts-jest`).

## Vorgehen bei neuen Findings

1. Bevorzugt: **Version anheben** (`requirements-dev.txt`, `constraints-runtime.txt`, `package.json` / Lockfile).
2. Wenn Fix unmöglich oder Risiko im konkreten Deployment vernachlässigbar: ID in **`pip_audit_allowlist.txt`** eintragen und **im PR** die Begründung beschreiben (Verlinkung auf Advisory).

## Verwandte Doku

- [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
- [`docs/LAUNCH_DOSSIER.md`](LAUNCH_DOSSIER.md), [`docs/ci_release_gates.md`](ci_release_gates.md)
- [`docs/OPS_QUICKSTART.md`](OPS_QUICKSTART.md)
