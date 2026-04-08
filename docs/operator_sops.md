# Operator-SOPs

Diese SOPs beschreiben den **taeglichen, reproduzierbaren Betrieb**. Sie
ergänzen `docs/LAUNCH_DOSSIER.md`, `docs/LaunchChecklist.md`,
`docs/shadow_burn_in_ramp.md`, `docs/prod_runbook.md` und
`docs/monitoring_runbook.md`.

## 1. Taeglicher Betrieb

### Ziel

Vor Handelsbeginn sicherstellen, dass Daten, Broker, Alerts, Forensik und
Operatorpfade gesund sind.

### Schritte

1. `bash scripts/healthcheck.sh`
2. `GET /v1/system/health`
3. Dashboard `/ops` lesen:
   - `Mirror-Freigabe (Approval Queue)`
   - `Live Mirrors & Divergenz`
   - `Kill-Switch`
   - `Drift & Pfad-Gates`
4. Offene Alerts pruefen:
   - `GET /v1/monitor/alerts/open`
   - `ops.alerts`
5. Wenn aktiv:
   - `kill_switch_active` -> kein Trading ohne Ursachenanalyse
   - `safety_latch_active` -> kein Live-Fire
   - `gateway_auth_failures_1h` oder `telegram_operator_errors_24h` -> Operatorpfad prüfen

### Abbruchbedingungen

- kritische offene Alerts
- Reconcile nicht sauber
- Shadow-Live-Mismatch nicht geklärt

## 2. Shadow-Auswertung

### Ziel

Nachvollziehen, ob `allow_trade`, `do_not_trade`, Stop-Budget, Spezialistenroute
und `candidate_for_live` qualitativ tragfaehig waren.

### Schritte

1. Dashboard `/signals`:
   - `trade_action`
   - `meta_trade_lane`
   - `specialist_router_id`
   - `exit_family_effective_primary`
   - Stop-Fragilitaet / Stop-Budget
2. Signal-Detail pruefen:
   - `Warum kein Trade?`
   - `Warum genau dieser Trade?`
   - `decision_control_flow.no_trade_path`
3. Falls `execution_id` existiert:
   - `/live-broker/forensic/[id]`
4. Ergebnisse in Burn-in-Matrix gegen `docs/shadow_burn_in_ramp.md` abgleichen

### Abbruchbedingungen

- No-Trade-Qualitaet unplausibel
- Stop-Budget blockiert strukturell
- Router-/Adversary-Dissent haeuft sich ungeklaert

## 3. Echtgeld-Freigabe (enge Mirror-Stufe)

### Ziel

Nur bereits qualifizierte `candidate_for_live`-Kandidaten kontrolliert in die
enge Echtgeld-Mirror-Stufe ueberführen.

### Voraussetzungen

- `EXECUTION_MODE=live`
- `STRATEGY_EXEC_MODE=manual`
- `LIVE_REQUIRE_EXECUTION_BINDING=true`
- `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true`
- `REQUIRE_SHADOW_MATCH_BEFORE_LIVE=true`
- `RISK_ALLOWED_LEVERAGE_MAX=7`
- `RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE=7`

### Schritte

1. In `/ops` nur Kandidaten aus der Startkohorte betrachten
2. Vor Freigabe pruefen:
   - `live_mirror_eligible=true`
   - `shadow_live_match_ok=true`
   - `operator_release_pending`
   - `live_execution_clear_for_real_money=true`
3. Freigabe nur ueber:
   - Telegram-Zweistufen-Pfad oder
   - Gateway `manual-action/mint` + `operator-release`
4. Danach Forensik fuer die `execution_id` pruefen

### Abbruchbedingungen

- Kandidat faellt aus Startkohorte
- `shadow_live_match_ok=false`
- `stop_fragility_0_1` / `stop_budget_outcome` kritisch

## 4. Notfall-Stopp

### Ziel

Sofortigen Schutz des Echtgeldpfads ohne Strategieumbau.

### Schritte

1. Kill-Switch oder Emergency-Flatten auslösen
2. `safety_latch_active` und Audit prüfen
3. Timeline lesen:
   - `gateway_audit`
   - `telegram_operator_actions`
   - `audit_trails`
4. Nur nach Ursachenanalyse wieder freigeben

### Abbruchbedingungen

- unklare offene Orders
- Reconcile-Drift
- ungeklärte Exchange-/Gateway-Fehler

## 5. Session-Checks

Vor jeder operativen Session dokumentieren:

1. Profil / Modus / Family-Allowlist
2. aktuelle Startkohorte
3. offene Incidents / bekannte Degradationen
4. letzte Operator-Freigaben und Reviews
5. geplante Änderungen: keine stillen Policy-Sprünge

## 6. Release-Tag

### Ziel

Release mit auditierbarem Artefakt und eindeutigem Betriebszustand.

### Schritte

1. `python tools/release_sanity_checks.py --strict`
2. relevante CI-Gates / lokale Kernchecks grün
3. `docs/LAUNCH_DOSSIER.md` und `docs/LaunchChecklist.md` gegen Ist-Stand prüfen
4. `bash scripts/deploy.sh` nur mit gesetzten Secrets und dokumentierter Revision
5. nach Deploy:
   - `bash scripts/healthcheck.sh`
   - `/ops`
   - `/live-broker`
   - `/monitor/alerts/open`

## 7. Modellpromotion

### Ziel

Champion-/Challenger-Änderungen nur mit Governance und nachvollziehbarem Rollback.

### Schritte

1. `docs/model_registry_v2.md` und `docs/model_lifecycle_governance.md` prüfen
2. Drift-/Burn-in-/Shadow-Evidenz gegen Promotion-Gates prüfen
3. Promotion nur mit dokumentiertem `changed_by` und Secret-geschützter Mutation
4. Nach Promotion:
   - Registry-Slots lesen
   - Shadow-/Drift-/No-Trade-Verhalten beobachten
   - ggf. Rollback-Pfad bereithalten

### Abbruchbedingungen

- fehlende Kalibrierung
- Drift hart blockiert
- keine belastbare Burn-in-Evidenz
