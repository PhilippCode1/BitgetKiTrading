# Operator-Onboarding-Checkliste

Diese Checkliste dient dazu, einen neuen Operator **sicher, reproduzierbar und
ohne implizites Wissen** in das System einzuführen.

## 1. Grundverständnis

- [ ] `docs/adr/ADR-0001-bitget-market-universe-platform.md` gelesen
- [ ] `docs/execution_modes.md` gelesen
- [ ] `docs/operator_status_language.md` gelesen
- [ ] verstanden: `allow_trade` ist nicht gleich Echtgeldfreigabe
- [ ] verstanden: `do_not_trade` ist ein korrekter Produktzustand, kein Fehler

## 2. Sicherheitsgrenzen

- [ ] keine Secrets in Browser, Chat oder Tickets
- [ ] Telegram darf keine Strategie, Modellgewichte, Playbooks oder Risk-Limits ändern
- [ ] Echtgeld nur über gebundene `execution_id` und operator-gated Freigaben
- [ ] Kill-Switch, Safety-Latch und Emergency-Flatten voneinander unterscheiden

## 3. Betriebsoberflächen

- [ ] Dashboard `/ops` lesen können
- [ ] Dashboard `/signals` lesen können
- [ ] Dashboard `/live-broker` lesen können
- [ ] Dashboard `/live-broker/forensic/[id]` lesen können
- [ ] Gateway sensitive read vs. mutation verstehen
- [ ] Telegram-Kommandos `/help`, `/status`, `/mute`, `/unmute`, `/exec_recent`, `/exec_show`, `/release_step1`, `/release_confirm`, `/release_abort`, `/emerg_step1`, `/emerg_confirm`, `/emerg_abort` einordnen

## 4. Täglicher Betrieb

- [ ] `bash scripts/healthcheck.sh` ausgeführt und interpretiert
- [ ] `/v1/system/health` verstanden
- [ ] `ops.alerts` / `GET /v1/monitor/alerts/open` verstanden
- [ ] `kill_switch_active` / `safety_latch_active` im Dashboard erkannt

## 5. Shadow-Auswertung

- [ ] Burn-in-Matrix aus `docs/shadow_burn_in_ramp.md` verstanden
- [ ] `meta_trade_lane`, `candidate_for_live`, `live_mirror_eligible`, `shadow_live_match_ok` sicher unterscheiden
- [ ] `decision_control_flow.no_trade_path` lesen können
- [ ] Stop-Budget- und Stop-Fragilitaetsfelder interpretieren können

## 6. Echtgeld-Mirror-Freigabe

- [ ] Voraussetzungen der Startkohorte verstanden
- [ ] Approval Queue nur für `operator_release_pending`-Kandidaten benutzt
- [ ] Release nur über Telegram- oder Gateway-Zweistufenpfad durchgeführt
- [ ] Nach Freigabe Forensik für dieselbe `execution_id` geprüft

## 7. Notfallpfade

- [ ] Kill-Switch-Runbook durchgespielt
- [ ] Emergency-Flatten-Runbook durchgespielt
- [ ] Safety-Latch-Release-Prozess verstanden
- [ ] Kein Resume ohne Ursachenanalyse

## 8. Release-Tag und Modellpromotion

- [ ] `docs/operator_sops.md` Abschnitt Release-Tag gelesen
- [ ] `docs/model_registry_v2.md` gelesen
- [ ] Promotion-/Rollback-Begriffe Champion / Challenger / Stable Checkpoint verstanden

## 9. Freigabe

- [ ] Operator kann ohne Hilfe erklären:
  - wann das System `shadow-only` bleiben muss
  - wann `do_not_trade` korrekt ist
  - wann `operator_release_pending` zu `operator_released` werden darf
  - wann ein No-Go und Ramp-Fallback vorliegt

## 10. URLs, TLS, Edge (Produktion)

- [ ] `docs/OPERATOR_HANDBOOK.md` und `docs/operator_urls_and_secrets.md` gelesen
- [ ] `APP_BASE_URL`, `FRONTEND_URL`, `CORS_ALLOW_ORIGINS`, `NEXT_PUBLIC_*` konsistent; Dashboard nach ENV-Aenderung neu gebaut
- [ ] Reverse-Proxy setzt `X-Forwarded-Proto` / `X-Forwarded-Host`; `GET /v1/deploy/edge-readiness` ohne Blocker
- [ ] `GET /health`, `GET /ready` (Gateway) und `GET /api/health` (Dashboard) fuer Monitoring eingetragen

## 11. Plaene, Nutzung, Support (falls COMMERCIAL_ENABLED)

- [ ] `docs/PRODUCT_PLANS_AND_USAGE.md` und `docs/commercial_transparency.md` gelesen
- [ ] `GET /v1/commerce/plans` und Usage-Summary mit Rollen `billing:read` getestet
- [ ] Support-/Status-Kanaele organisatorisch geklaert (`docs/EXTERNAL_GO_LIVE_DEPENDENCIES.md`, optional `SUPPORT_EMAIL` / `STATUS_PAGE_URL` in `.env.production`)
