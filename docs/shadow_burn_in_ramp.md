# Shadow-Burn-in und Live-Ramp

Dieses Dokument definiert den **institutionellen Uebergang** von einem starken
Code-/Teststand zu einem kontrollierten Betriebsmodus:

1. erst **shadow-only**
2. dann **operator-gated live mirror** fuer eng begrenzte KI-Plaene
3. danach nur **evidenzbasierte** Erweiterung von Hebel, Familien und Playbook-Typen

Die technische Quelle der Wahrheit bleibt das bestehende Monorepo:

- Marktuniversum / Architektur: `docs/adr/ADR-0001-bitget-market-universe-platform.md`
- Modi und Gates: `docs/execution_modes.md`
- Risk-/Live-Ramp: `docs/risk_governor.md`
- Shadow-vs-Live: `docs/shadow_live_divergence.md`
- Live-Broker: `docs/live_broker.md`
- Monitoring / Forensik: `docs/monitoring_runbook.md`, `docs/runbooks/forensics_and_incidents.md`

## Zielbild

- **LLM** bleibt Analyse-/Explain-/Review-Helfer, nie alleinige Trading-Instanz.
- **Trading-Freigabe** bleibt durch Safety Gates, Risk Engine, Spezialisten, Router, Stop-Budget und No-Trade-Logik begrenzt.
- **Telegram** bleibt Informations-, Bestaetigungs- und Manual-Execution-Kanal. Keine Strategie- oder Risk-Mutation per Chat.
- **Live** startet nicht vollautonom. Zuerst laufen nur enge, operator-gated Mirror-Pfade fuer hochqualitative, auditable KI-Plaene.

## Phase 1: Shadow-Burn-in

### Pflichtkonfiguration

Shadow-Burn-in ist nur gueltig, wenn mindestens diese Gating-Kombination aktiv ist:

- `EXECUTION_MODE=shadow`
- `STRATEGY_EXEC_MODE=manual`
- `SHADOW_TRADE_ENABLE=true`
- `LIVE_TRADE_ENABLE=false`
- `LIVE_BROKER_ENABLED=true`
- `LIVE_REQUIRE_EXECUTION_BINDING=true`
- `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true`
- `REQUIRE_SHADOW_MATCH_BEFORE_LIVE=true`
- `RISK_ALLOWED_LEVERAGE_MAX=7`
- `RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE=7`

### Repräsentative Burn-in-Matrix

Burn-in darf nicht nur `BTCUSDT`-Pfad beobachten. Er muss den **real im Konto / in der Bitget-Metadata-Lage exponierten** Scope abdecken.

#### Marktfamilien und Instrumenttypen

- **Spot**: mindestens 2 liquide USDT-Quote-Instrumente, z. B. `BTCUSDT`, `ETHUSDT`, sofern Discovery/Katalog sie als `trading_enabled` fuehrt
- **Margin**: mindestens 1 `isolated`- und 1 `crossed`-Pfad, sofern Konto und Metadata beide Modi real tragen
- **Futures**: `USDT-FUTURES` verpflichtend; `USDC-FUTURES` und `COIN-FUTURES` nur, wenn der aktuelle Katalog sie real exponiert
- **Weitere Kategorien** wie index-/CFD-/stock-linked nur als read-/analysis-visible, bis echte Execution-Adapter und Discovery-Evidenz vorliegen

#### Regime und Spezialistenrouten

Burn-in ist nur repraesentativ, wenn je aktivem Family-/Instrumenttyp beobachtet wurde:

- `trend_continuation`
- `breakout`
- `mean_reversion`
- `range_rotation`
- `volatility_compression_expansion`
- `news_shock` oder event-getriebener Stresstag, sofern im Beobachtungszeitraum real auftritt

Zusätzlich muessen im Audit sichtbar sein:

- mindestens ein `candidate_for_live`-Pfad
- mindestens ein `shadow_only`-/`paper_only`-Pfad
- mindestens ein sauber begruendeter `do_not_trade`-Pfad
- Spezialisten-/Router-Sicht ueber `reasons_json.specialists.router_arbitration`
- `decision_control_flow.no_trade_path`

#### Beobachtungsdauer

Burn-in ist erst belastbar, wenn fuer den aktiven Shadow-Kohortensatz gleichzeitig gilt:

- mindestens **14 aufeinanderfolgende Kalendertage**
- mindestens **3 unterschiedliche Session-Cluster** im Beobachtungsfenster
- mindestens **1 dokumentierter Stress-/Event-Tag**, falls im Zeitraum real aufgetreten

### Datenbasierter Burn-in-Report (10/10-Evidence)

Fuer die betriebliche Freigabelinie dient ein **auswertbares, reproduzierbares**
Zertifikat, das die Postgres-Tabellen (nicht ad-hoc Logs) im Rückblick
belegt. Das Skript

`scripts/verify_shadow_burn_in.py`

führt automatisierte Checks im gewählten **Zeitfenster** (Standard **72h**)
durch u.a.:

- `live.execution_decisions` (Blockierungen, Fat-Finger-artige
  Reason/Regex-Treffer)
- `paper.strategy_events` mit `AUTO_BLOCKED` (Hinweiszähler, kein
  harter Abbruch)
- `ops.alerts` (offen + warn/critical im Fenster) als
  **P0/P1-äquivalenter** Monitoring-Signal-Stack
- `ops.stream_checks` / `ops.service_checks` (Lag, Latency, `status=fail`)
- `ops.service_checks` `check_type=health` (max. Lücke je Service als
  **Heartbeat-Integrität**; konfigurierbares Obergabenniveau)
- `live.audit_trails` `severity=critical` im Fenster

**Nutzung:**

```text
# DATABASE_URL: Staging/Shadow-Postgres; alternativ: --env-file <pfad>
python scripts/verify_shadow_burn_in.py --hours 72 --strict \
  --output-md reports/shadow_burn_in.md --output-json reports/shadow_burn_in.json
```

Wichtige Flags:

- `--env-file` / `--database-url` (Default: `DATABASE_URL`)
- `--strict` — fehlende Kerntabellen oder leere Kerndaten: **`NO_EVIDENCE`**, Exitcodes **0/1/2** (PASS / FAIL / NO_EVIDENCE)
- `--output-json` — u. a. `verdict`, `git_sha`, `report_sha256` (SHA-256 des Markdown-Reporttextes)
- `--min-decisions` / `--min-signals` / `--max-reconcile-fail-ratio` / `--max-ticker-stale-sec` / …
- `--max-pipeline-lag-ms`, `--max-heartbeat-gap-sec`, Slippage-Grenzen — siehe `python … --help`
- Doku-Template: `docs/production_10_10/04_shadow_burn_in_certificate.md`

**Ausgabe:** Markdown auf stdout und optional Dateien. **stderr** kurz `[PASS/GO]`, `[NO-GO/FAIL]`, oder `[NO_EVIDENCE]`. Nicht ersetzen: **Kalender-/Kohortenmatrix** und ENV-Nachweis; das Skript liefert **DB-Evidenz** dazu.

## Harte Freigabekriterien vor Echtgeld-Mirror

Alle Kriterien muessen gleichzeitig gruen sein. Sonst bleibt das System **shadow-only**.

### 1. Data Health

- keine offenen kritischen `ops.alerts`
- keine aktiven `DataStale*`- oder `SignalThroughputStalled`-Warnungen im Freigabefenster
- `GET /v1/system/health` ohne degradierte Kernpfade fuer die betrachtete Familie / das betrachtete Instrument

### 2. Route Stability

- `signal_router_switches_24h < THRESH_SIGNAL_ROUTER_SWITCHES_24H_WARN`
- keine ungeklärten Router-Wechsel in Stichproben aus `app.signals_v1.reasons_json.specialists.router_arbitration`

### 3. No-Trade Quality

- `signal_do_not_trade_ratio_1h < THRESH_SIGNAL_DO_NOT_TRADE_RATIO_WARN`, ausser waehrend dokumentierter Marktstressfenster
- Stichprobe aus mindestens 20 `do_not_trade`-Faellen:
  - `decision_control_flow.no_trade_path` plausibel
  - keine offensichtliche Diskrepanz zwischen Explain, Risk und Router-Veto

### 4. Stop Fragility / Ausfuehrbarkeit

- `signal_stop_fragility_p90_24h < THRESH_STOP_FRAGILITY_P90_WARN`
- keine Mirror-Kandidaten mit `stop_budget_outcome=blocked`
- keine Kandidaten, deren `stop_distance_pct` unter `stop_min_executable_pct` liegt

### 5. Shadow-Live Divergence

- `REQUIRE_SHADOW_MATCH_BEFORE_LIVE=true`
- keine offenen `shadow_live_assessment_mismatch_24h`
- fuer die Mirror-Kohorte: keine ungeklärten `shadow_live_hard_violations`

### 6. Reconcile Cleanliness

- `live_reconcile_drift_total` im Cutover-Fenster = 0 oder unter dokumentierter Operator-Ausnahme
- kein aktiver `Safety-Latch`
- keine ungeklärten `live_critical_audits_24h`

### 7. Incident-Free Runtime

- keine P0-/P1-Incidents im Freigabefenster
- keine `telegram_operator_errors_24h`
- keine `gateway_auth_failures_1h`

### 8. Operator Readiness

Vor Echtgeld-Mirror muss ein Drill erfolgreich absolviert werden:

- Approval Queue in `/ops` gelesen
- `live-broker/forensic/[id]` fuer mindestens eine Shadow-Execution auditiert
- Manual-Action-/Operator-Release-Kette dokumentiert
- Kill-Switch-, Safety-Latch- und Emergency-Flatten-Runbook verstanden

## Phase 2: Enge Echtgeld-Mirror-Logik

Echtgeld startet **nicht** als vollautonomer Modus. Die erste Live-Stufe ist ein
**operator-gated mirror** fuer eine enge, hochwertige Kohorte.

### Mirror-Kandidaten muessen gleichzeitig erfuellen

- `trade_action=allow_trade`
- `decision_state` nicht `rejected`
- `meta_trade_lane=candidate_for_live`
- `router_operator_gate_required=true`
- `live_execution_clear_for_real_money=true`
- `live_mirror_eligible=true`
- `shadow_live_match_ok=true`
- `playbook_decision_mode=selected`
- `RISK_ALLOWED_LEVERAGE_MAX=7`
- `recommended_leverage <= 7`

### Anfangskohorte

Die erste Echtgeldfreigabe bleibt eng:

- **Family:** nur `futures`
- **Product-Type:** nur `USDT-FUTURES`
- **Symbole:** nur explizite Live-Allowlist, initial `BTCUSDT`
- **Playbook-Familien:** initial nur liquide, directional Familien aus `shared_py.playbook_registry`, z. B.
  - `trend_continuation`
  - `breakout`
  - `pullback`

Die folgenden Familien bleiben zunaechst **shadow-only**, bis Evidenz vorliegt:

- `mean_reversion`
- `range_rotation`
- `carry_funding`
- `news_shock`
- `session_open`
- `time_window_effect`
- alle Margin-/Spot-Live-Pfade

## No-Go / Fallback auf Shadow-only

Sobald eine der Bedingungen eintritt, faellt das System wieder in **shadow-only**:

- `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN` oder `LIVE_REQUIRE_EXECUTION_BINDING` sind nicht aktiv
- `REQUIRE_SHADOW_MATCH_BEFORE_LIVE=false`
- `signal_router_switches_24h >= THRESH_SIGNAL_ROUTER_SWITCHES_24H_WARN`
- `signal_specialist_disagreement_ratio_24h >= THRESH_SIGNAL_SPECIALIST_DISAGREEMENT_RATIO_WARN`
- `signal_stop_fragility_p90_24h >= THRESH_STOP_FRAGILITY_P90_WARN`
- `shadow_live_assessment_mismatch_24h > 0`
- `live_reconcile_drift_total >= THRESH_RECONCILE_DRIFT_TOTAL_WARN`
- aktiver Kill-Switch oder Safety-Latch
- `gateway_auth_failures_1h >= THRESH_GATEWAY_AUTH_FAILURES_1H_WARN`
- `telegram_operator_errors_24h >= THRESH_TELEGRAM_OPERATOR_ERRORS_24H_WARN`
- ungeklärte kritische Audits oder Incident-Kette nicht mehr `incident-free`

## Phase 3: Evidenzbasierte Ramp-Strategie

Erweiterungen erfolgen nur stufenweise und nur mit dokumentierter Evidenz.

### R0 — Shadow-only

- alle real exponierten Familien beobachten
- keine echten Orders

### R1 — Mirror konservativ

- `futures`
- `USDT-FUTURES`
- `BTCUSDT`
- Playbook-Familien: `trend_continuation`, `breakout`, `pullback`
- `RISK_ALLOWED_LEVERAGE_MAX=7`
- `RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE=7`

### R2 — Mirror erweitert

Nur nach stabilem R1:

- zweites liquides Futures-Instrument
- ggf. zweite directional Playbook-Familie
- Hebel nur innerhalb des naechsten Risk-Governor-Tiers, also **maximal 14**

### R3 — Produkt-/Family-Erweiterung

Nur nach dokumentierter Evidenz:

- `USDC-FUTURES` oder `COIN-FUTURES`, falls Discovery/Katalog und Kosten-/Delivery-Pfade stabil sind
- Spot/Margin-Live erst nach eigener Burn-in-Kohorte, weil Short-/Reduce-Only-/Loan-Semantik abweicht

### R4 — Hebel- und Kohorten-Ausbau

Weitere Hebelerhoehungen muessen sich an den bestehenden Risk-Governor-Stufen orientieren:

- Tier D: `7`
- Tier C: `14`
- Tier B: bis `35`
- Tier A: bis `75`

Eine Erhoehung ist nur erlaubt, wenn `leverage_escalation_approved=true` und
`measurably_stable_for_escalation=true` im Risiko-Snapshot begruendbar sind.

## Operator-Artefakte fuer diesen Schritt

- Launch-Dossier / Checkliste: `docs/LAUNCH_DOSSIER.md`, `docs/LaunchChecklist.md`
- Modi / Broker: `docs/execution_modes.md`, `docs/live_broker.md`
- Monitoring / Forensik: `docs/monitoring_runbook.md`, `docs/runbooks/forensics_and_incidents.md`
- Operator-Sicht: `/ops`, `/live-broker`, `/live-broker/forensic/[id]`

## Abschlussbedingung fuer diese Stufe

Diese Stufe ist **nicht** abgeschlossen, solange:

- Burn-in-Kohorte nicht vollstaendig repraesentativ beobachtet wurde
- harte Freigabekriterien offen sind
- Live-Mirror ohne operator-gated Binding moeglich waere
- No-Go-/Fallback-Bedingungen nicht dokumentiert und getestet sind
