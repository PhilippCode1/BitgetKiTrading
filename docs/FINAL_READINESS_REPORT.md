# Final Readiness Report

## Zweck

Dieses Dokument ist der **ehrliche Abschlussstand** des Prompt-Packs. Es trennt:

- was im Monorepo fachlich und betrieblich gehaertet wurde
- was bewusst konservativ bleibt
- welche Familien und Ramp-Stufen aktuell freigegeben sind
- welcher **Go-Live-Zustand** technisch vorliegt
- welche Punkte noch **intern offen** sind
- welche Punkte **rein extern** bleiben

Management nutzt ausschließlich **`docs/LaunchChecklist.md`** als abnahmefähige Single Source of Truth (mit Signoff-Tabelle).  
Technische Gates: `python tools/release_sanity_checks.py` muss im Release-Pfad grün laufen; Burn-in-„Zertifikat“: `python scripts/verify_shadow_burn_in.py` (siehe `docs/shadow_burn_in_ramp.md`).

Es ersetzt nicht:

- `docs/LAUNCH_DOSSIER.md`
- `docs/LaunchChecklist.md` (laufend zu pflegen)
- `docs/shadow_burn_in_ramp.md`
- `docs/operator_sops.md`

## Was gehaertet wurde

### Architektur / Fachkern

- Family-aware Zielarchitektur fuer `spot`, `margin`, `futures` ist kanonisch beschrieben
- Spezialisten-System mit Family-, Regime-, Playbook- und Router-/Adversary-Pfaden ist dokumentiert und sichtbar
- deterministische Risk-, Stop-Budget- und Exit-Logik ist ueber Doku, Forensik und UI verankert
- `do_not_trade` bleibt ein legitimer Zielzustand und wird nicht als Fehlfunktion behandelt

### Operatorischer Echtgeldpfad

- Echtgeld startet als **operator-gated mirror**, nicht als Vollautonomie
- gebundene `execution_id` als Pflichtressource
- `LIVE_REQUIRE_EXECUTION_BINDING`, `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN` und `REQUIRE_SHADOW_MATCH_BEFORE_LIVE` als technische Echtgeld-Firewall
- Approval Queue, Live Mirrors, Divergenz- und Trade-Forensik im Dashboard
- Telegram- und Gateway-Freigaben arbeiten beide zweistufig und gebunden

### Forensik / Monitoring

- Trade-Timeline von Signal-/Marktkontext ueber Release, Order/Fills bis Review
- SQL-/Prometheus-SLOs fuer Route-Instabilitaet, Specialist-Disagreement, Stop-Fragilitaet, No-Trade-Spikes, Telegram-Operatorfehler und Auth-Anomalien
- produktionsnahe Redaction fuer Forensik, Gateway-Audit und Telegram-Operatorpfade

### Tests / Release-Hygiene

- breitere Family-/Stop-/Mirror-/Auth-/SLO-Tests
- Dashboard ohne `passWithNoTests`, mit Coverage-Gate
- zentraler Python-Runtime-Constraints-Pfad
- **Standalone-Dashboard (P82):** `output: "standalone"` in `apps/dashboard/next.config.js`, Docker-Runtime kopiert `build/standalone` + `build/static` (kein pnpm-Workspace-Root, kein `next start` mit vollstaendigem Monorepo-`node_modules`); Image-Groesse typisch deutlich unter 500MB
- strengere Release-Sanity-Pruefungen
- Paper-Contract-Konfiguration faellt in shadow-/production-nahen `live`-Pfaden nicht mehr still auf Fixtures zurueck

## Was bewusst konservativ bleibt

- LLM bleibt Analyse-/Explain-/Review-Helfer, nie alleinige Trading-Instanz
- Startprofil fuer Shadow und Production bleibt `EXECUTION_MODE=shadow`
- erste Echtgeldstufe bleibt `STRATEGY_EXEC_MODE=manual`
- Starthebel bleibt `7`
- Startkohorte bleibt eng und explizit gebunden
- `do_not_trade` gewinnt immer gegen Wunsch nach Aktivitaet

## Aktuell freigegebene Familien / Ramp-Stufen

### Beobachtungs- und Burn-in-Scope

- `spot`
- `margin`
- `futures`

Diese Familien duerfen im Burn-in und in der Shadow-Auswertung repraesentativ beobachtet werden, soweit Konto und Bitget-Metadaten sie real exponieren.

### Echtgeld-Mirror Startzustand

Aktuell dokumentierter konservativer Startzustand:

- **Family:** `futures`
- **Product-Type:** `USDT-FUTURES`
- **Symbol-Allowlist (Start):** `BTCUSDT`
- **Meta-Lane:** `candidate_for_live`
- **Mirror-Kriterium:** `live_mirror_eligible=true`
- **Shadow-Kriterium:** `shadow_live_match_ok=true`
- **Risk-Kriterium:** `live_execution_clear_for_real_money=true`
- **Freigabe:** `operator_release_pending` -> `operator_released`
- **Hebel:** `RISK_ALLOWED_LEVERAGE_MAX=7`
- **Live-Ramp-Cap:** `RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE=7`

### Ramp-Stufen

- `R0`: `shadow-only`
- `R1`: operator-gated mirror fuer enge Futures-Startkohorte
- `R2`: erweiterte Mirror-Kohorte bei stabiler Evidenz
- `R3`: Family-/Product-Type-Erweiterung nur nach Discovery-/Delivery-Evidenz
- `R4`: Hebelerweiterung nur nach Risk-Governor- und Burn-in-Evidenz

## Exakter Go-Live-Zustand

Technisch ist der Stack auf folgenden Zustand vorbereitet:

- Shadow-produktionsnaher Betrieb
- operator-gated Mirror-Freigabe fuer bestehende `execution_id`
- keine vollautonome Echtgeldfreigabe
- keine Chat-basierte Strategie- oder Risk-Mutation
- konservativer Starthebel
- dokumentierte Kill-Switch-, Safety-Latch-, Emergency- und Recovery-Pfade

Anders gesagt:

- **Go fuer Shadow-Burn-in:** ja
- **Go fuer enge Echtgeld-Mirror-Stufe:** technisch vorbereitet, aber nur nach Burn-in-Evidenz und formaler Freigabe
- **Go fuer vollautonomen Echtgeldbetrieb:** nein

## Interne Restliste (akzeptiert / iterativ — kein P0-Blocker)

**P83 (2026-04-24):** Die frueheren **„major“-Drift**-Punkte (Doku, BTCUSDT-Default-Narrative, widersprüchliche Audit-Phasen) sind in **REPO_FREEZE_GAP_MATRIX** und **CODEBASE_DEEP_EVALUATION** als **P0-geschlossen** geführt. Verbleibend sind **P1/P2- oder Dauerbaustellen**, keine „blockierenden Lücken” gegen einen Software-Freigabestand:

- Coverage-Gates und pytest vollumfänglich: weiterhin Sache der CI-ENV, siehe `docs/TESTING_AND_EVIDENCE.md`.
- Vollstack-Replay-Determinismus (inkl. LLM-Nebenpfade): iterativ, siehe `docs/REPO_FREEZE_GAP_MATRIX.md` und `docs/replay_determinism.md`.
- **SYSTEM_AUDIT_MASTER.md:** Master mit Phasen 1–18 **COMPLETED** (2026-04-24); ersetzt die alte reine Verweisform ohne Phasenstatus.

## Reine externe Blocker

Diese Punkte sind **nicht** mehr primär Produktentwicklung:

- echte Secrets und deren Rotation
- Vault/KMS/Secret-Manager-Injektion
- Domain, TLS, Ingress, WAF
- Exchange-Konto, Kapitalgrenzen, Kontofreigaben
- rechtliche/compliance-seitige Freigaben
- formale Live-Sign-offs
- produktiver Alertmanager / Paging / On-Call
- Backup-/Restore-Nachweise im Betriebsumfeld

## Gesamturteil

Der Stack ist deutlich naeher an **institutionellem Dauerbetrieb** als an einer
einfachen Demo:

- autonome Fachspezialisten statt Einheitsmodell
- harte No-Trade- und Risk-Policy
- enge, aber marktmechanisch realistische Stop-Disziplin
- operator-gated Echtgeldpfad
- nicht manipulierbarer Strategiekern
- ausgebaute Forensik, SOPs, Onboarding- und Ramp-Vertraege

Fuer **Software-Freigabe** im Monorepo ist **P0 erledigt**; **voll** „release-grade“ im Sinn
von Live-Börse, organisatorischem Soak und externen Unterschriften bleibt am **LaunchChecklist**
Management-Teil und **reinen externen** Blockern gebunden (`docs/adr/ADR-0010-roadmap-accepted-residual-risks.md`).
