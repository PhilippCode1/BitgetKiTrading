# Evidence Matrix

Diese Markdown-Datei ist die menschenlesbare Sicht auf die maschinenlesbare
Matrix in `docs/production_10_10/evidence_matrix.yaml`. Die YAML ist die
kanonische Quelle fuer Checker, Reports und Live-Blocker-Auswertung.

Scope: private deutsche Main-Console-Anwendung fuer Philipp Crljic. Keine
Billing-/Commercial-Gates als Pflichtkategorie, keine Customer-UI als
Verkaufsprodukt, keine Tenant-Isolation als Multi-Kunden-Verkaufsarchitektur,
keine Payment-Provider- oder Customer-Contract-Checks.

## Checker

```bash
python tools/check_10_10_evidence.py
python tools/check_10_10_evidence.py --strict
python tools/check_10_10_evidence.py --json
python tools/check_10_10_evidence.py --write-report docs/production_10_10/evidence_status_report.md
```

Ohne `--strict` validiert der Checker Schema, Statuswerte, Pflichtkategorien,
Evidence-Dateien und Live-Blocker, gibt aber bei valider Matrix Exit-Code 0.
Mit `--strict` wird jeder nicht verifizierte Live-Blocker zum Exit-Code 1.

## Pflichtkategorien

| ID | Titel | Status | Blockiert Live | Severity | Naechste Aktion |
| --- | --- | --- | --- | --- | --- |
| `private_owner_scope` | Private Owner Scope | `verified` | nein | P1 | Scope bei jeder UI- und Trading-Aenderung gegenpruefen. |
| `main_console_information_architecture` | Main Console Information Architecture | `implemented` | ja | P1 | Dashboard-Routen inventarisieren und Main-Console-Konsolidierungsplan erzeugen. |
| `german_only_ui` | German-only UI | `partial` | ja | P1 | UI-Textscanner und deutsche Main-Console-Copy-Review ergaenzen. |
| `bitget_asset_universe` | Bitget Asset Universe | `implemented` | ja | P0 | Asset-Freigabe und Tests pro Asset-Familie mit Evidence verknuepfen. |
| `instrument_catalog` | Instrument Catalog | `implemented` | ja | P0 | Katalogfrische und Exchange-Abgleich als Release-Evidence ablegen. |
| `asset_quarantine_and_delisting` | Asset Quarantine and Delisting | `partial` | ja | P0 | Asset-Quarantine-Modell und Fail-closed-Tests ergaenzen. |
| `market_data_quality_per_asset` | Market Data Quality per Asset | `partial` | ja | P0 | Per-Asset-Datenqualitaetsmatrix und Tests an Live-Broker-Gates koppeln. |
| `liquidity_spread_slippage_per_asset` | Liquidity, Spread and Slippage per Asset | `partial` | ja | P0 | Liquiditaetsgate pro Asset-Klasse maschinenlesbar machen. |
| `asset_risk_tiers` | Asset Risk Tiers | `partial` | ja | P0 | Asset-Risk-Tier-Datei und Validator erstellen. |
| `multi_asset_order_sizing` | Multi-Asset Order Sizing | `partial` | ja | P0 | Multi-Asset-Sizing-Evidence pro Asset-Klasse ergaenzen. |
| `portfolio_risk` | Portfolio Risk | `partial` | ja | P0 | Owner-Limits und aktuelle Test-Evidence fuer Portfolio-Risk archivieren. |
| `strategy_validation_per_asset_class` | Strategy Validation per Asset Class | `partial` | ja | P0 | Asset-Klassen-Validierungsberichte erzeugen und verlinken. |
| `live_broker_fail_closed` | Live Broker Fail-Closed | `implemented` | ja | P0 | Aktuelle Gate-Test-Evidence mit dieser Matrix verknuepfen. |
| `order_idempotency` | Order Idempotency | `partial` | ja | P0 | Order-Idempotency-Report und Tests explizit referenzieren. |
| `reconcile_safety` | Reconcile Safety | `partial` | ja | P0 | Reconcile-Divergenz-Evidence und Runbook konsolidieren. |
| `kill_switch_safety_latch` | Kill Switch and Safety Latch | `partial` | ja | P0 | Drill-Evidence fuer Kill-Switch und Safety-Latch archivieren. |
| `emergency_flatten` | Emergency Flatten | `external_required` | ja | P0 | Emergency-Flatten-Drill mit Git-SHA, Umgebung und PASS erzeugen. |
| `bitget_exchange_readiness` | Bitget Exchange Readiness | `external_required` | ja | P0 | Read-only-/Demo-Abnahme und Key-Permission-Evidence extern archivieren. |
| `env_secrets_profiles` | ENV and Secrets Profiles | `partial` | ja | P0 | Runtime-Secret-Store- und Rotation-Evidence extern nachweisen. |
| `observability_slos` | Observability and SLOs | `partial` | ja | P1 | SLOs mit Main-Console-Go/No-Go und Alert-Drill verknuepfen. |
| `alert_routing` | Alert Routing | `partial` | ja | P1 | Realen Alert-Drill ohne Secret-Leak archivieren. |
| `backup_restore` | Backup and Restore | `partial` | ja | P0 | Staging-Restore mit RTO/RPO und PASS erzeugen. |
| `shadow_burn_in` | Shadow Burn-in | `external_required` | ja | P0 | Realen Shadow-Burn-in-Bericht mit PASS und SHA256 ablegen. |
| `disaster_recovery` | Disaster Recovery | `partial` | ja | P0 | End-to-end DR-Drill fuer Live-relevante States dokumentieren. |
| `audit_forensics` | Audit and Forensics | `partial` | ja | P0 | Audit-/Forensics-Evidence pro Order-Lifecycle verlinken. |
| `frontend_main_console_security` | Frontend Main Console Security | `partial` | ja | P0 | Main-Console-Security-Testplan ohne Customer-Verkaufsfokus erstellen. |
| `admin_access_single_owner` | Admin Access Single Owner | `partial` | ja | P0 | Single-Owner-Admin-Policy und Tests aus Legacy-Rollenmodell ableiten. |
| `deployment_parity` | Deployment Parity | `partial` | ja | P1 | Staging-/Production-Paritaetsreport fuer private Main Console erzeugen. |
| `supply_chain_security` | Supply Chain Security | `partial` | ja | P1 | Aktuelle Supply-Chain-Audit-Evidence fuer Release ablegen. |
| `final_go_no_go_scorecard` | Final Go/No-Go Scorecard | `external_required` | ja | P0 | Alle nicht verifizierten Live-Blocker schliessen und Owner-Go/No-Go dokumentieren. |

## Legacy-Scope

Alte Billing-, Customer-, Commercial- oder Tenant-Verkaufsartefakte sind nicht
Teil dieser Pflichtmatrix. Wenn bestehende Tools oder Codepfade noch davon
abhaengen, werden sie als Legacy-Risikoflaeche behandelt, bis sie inventarisiert,
als out-of-scope markiert und sicher konsolidiert oder entfernt sind.
