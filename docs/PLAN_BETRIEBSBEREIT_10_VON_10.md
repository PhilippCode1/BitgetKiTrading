# Plan: Anwendung in 10 Schritten auf 10/10 Betriebsbereitschaft

Dieses Dokument definiert **realistische** Zielbilder, eine **aktuelle Einschätzung** und **zehn aufeinander aufbauende Schritte** bis zu einem Zustand, der intern als **10/10 betriebsbereit** gelten kann. Es bezieht sich auf das **gesamte** Monorepo (Pipeline, Gateway, Broker, Dashboard, KI-Strecke), nicht nur auf eine Einzelfunktion.

**Verwandte Dateien:** `PRODUCT_STATUS.md`, `release-readiness.md`, `docs/LAUNCH_DOSSIER.md`, `docs/LaunchChecklist.md`, `README.md`.

---

## Was „10/10 betriebsbereit“ hier bedeutet (ohne Illusionen)

**10/10** heißt in diesem Plan **nicht** „null Fehler für immer“, sondern:

| Dimension             | 10/10 heißt                                                                                                     |
| --------------------- | --------------------------------------------------------------------------------------------------------------- |
| **Verfügbarkeit**     | Definierte SLOs (z. B. API-Gateway, kritische Lesepfade), Messung aktiv, Eskalation bei Verletzung.             |
| **Wiederherstellung** | Backups, Wiederanlauf, Runbooks getestet (mindestens Tischübung + ein realer Restore-Test).                     |
| **Sicherheit**        | Secrets aus Store, Rotation geklärt, kein Klartext-Default in Prod, Auth wie in `docs/api_gateway_security.md`. |
| **Änderbarkeit**      | CI grün auf `main`, Releases reproduzierbar, Rollback-Strategie dokumentiert.                                   |
| **Transparenz**       | Logs/Metriken/Traces für kritische Ketten; Operator weiß, wo er hinschaut.                                      |
| **Produktrisiko**     | Shadow-/Live-Gates laut Dossier; keine „stillen“ Live-Schalter.                                                 |
| **Nutzer/KI**         | Sichtbare Funktionen entsprechen der Doku; KI-Strecke in Staging verifiziert, Fehler verständlich.              |

**10/10 ist ein Zielzustand**, der **organisatorische** Freigaben (Compliance, Bitget, interne Policy) voraussetzt — das Repo kann die Software liefern, nicht die Genehmigungen ersetzen.

---

## Aktuelle Bewertung (Stand: P83 — Doku-Paritaet, konsolidiert mit `PRODUCT_STATUS.md`)

Grobe Skala: **1** = nur Code/Doc, **5** = lokal/Team stabil nutzbar, **8** = Staging mit SLO/Alerts, **10** = **Software- und Doku-Stand** im Monorepo entspricht der Zieldefinition; **operativer** Live-Handel bleibt **eurer** Checkliste (Secrets, Bitget, Recht) überlassen.

| Bereich                        | Score (0–10) | Kurzbegründung                                                                                                                                                       |
| ------------------------------ | ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Architektur & Codebasis**    | **10**       | Service-Grenzen, Multi-Asset-Factory, Gateway, Broker, Engines, Dashboard-Standalone; P83 Gate-Master vollstaendig.                                                    |
| **Lokale / Compose-Fähigkeit** | **9**        | `README` / `LOCAL_START_MINIMUM`; reale Maschine/ENV bleibt Host-Sache, nicht fehlendes Repo.                                                                         |
| **Staging = Prod-ähnlich**     | **9**        | Templates und Paritaets-Regeln dokumentiert; konkrete Staging-URL muss befuellt werden.                                                                              |
| **Secrets & Konfiguration**    | **9**        | Matrix, Validatoren, keine Secrets im Repo; Rotation = Betrieb.                                                                                                     |
| **Tests & Automatisierung**    | **9**        | CI-Gates, pytest, Dashboard-Jest; 100% Browser-Flaeche optional iterativ.                                                                                                    |
| **Observability & Alerting**   | **9**        | Optional Observability-Profil; Monitor-Engine integriert.                                                                                                            |
| **Runbooks & On-Call**         | **9**        | Umfangreiche Runbooks; Uebung = org.                                                                                                                                |
| **Sicherheit & Härtung**       | **9**        | Interne API-Keys, BFF, Supply-Chain-Gate; Pen-Test extern.                                                                                                        |
| **Produkt/KI-Kohärenz**        | **9**        | BFF, Allowlist, Operator-Pfade.                                                                                                                                      |
| **Go-Live / Live-Trading (Repo)** | **10**   | `LaunchChecklist` technisch [x], `REPO_FREEZE_GAP_MATRIX` P0 geschlossen, `CODEBASE_DEEP_EVALUATION` angepasst.                                                    |

**Gesamteinschätzung (Software/Doku-Monorepo):** **10/10** fuer den **Repo-Umfang**; vollwertiger **Börsen-Live-Go** = zusaetzlich Management-Signoff in `docs/LaunchChecklist.md` und reale Burn-in-Daten.

---

## Die 10 Schritte zu 10/10

Jeder Schritt hat: **Ziel**, **Konkrete Aktivitäten**, **Exit-Kriterium** (wann der Schritt als erledigt gilt).

---

### Schritt 1 — Baseline: „Grün auf einem Referenz-Stack“

**Ziel:** Ein definierter Pfad (z. B. Docker Compose oder euer Standard-Skript) startet **ohne Rätselraten** und liefert grüne Healths für Gateway, DB, Redis, mindestens einen Markt-/Signal-Pfad.

**Aktivitäten:**

- `.env.local` / Staging-ENV durch `tools/validate_env_profile.py` oder Projekt-Standard validieren.
- `scripts/healthcheck.sh` bzw. `pnpm stack:check` / `dev_up` laut README durchziehen.
- **Dashboard:** `DASHBOARD_GATEWAY_AUTHORIZATION` minten, Next neu starten, `/console/health` ohne 503 durch BFF.

**Exit-Kriterium:** Checkliste (1 Seite) im Team: „So starten wir den Referenz-Stack“ + ein Screenshot oder Log-Auszug „alle kritischen Checks grün“.

**Score-Hebel:** +0,5 bis +1,0 (von „es geht mal“ zu „reproduzierbar“).

---

### Schritt 2 — Staging-Umgebung mit Parität zur Produktion

**Ziel:** Eine Umgebung, die **dieselbe** Topologie wie Prod hat (oder dokumentierte Abweichungen), keine „localhost-Sonderlogik“ ohne Dokumentation.

**Aktivitäten:**

- Staging-URLs in ENV: `APP_BASE_URL`, `API_GATEWAY_URL`, `FRONTEND_URL`, `CORS_ALLOW_ORIGINS`, interne `HEALTH_URL_*` auf **Staging-Hostnamen**.
- Gleiche Secret-**Quelle** wie Prod (nur andere Werte).
- Smoke: ein Operator öffnet Dashboard Staging und führt **Health + einen Lesepfad** (z. B. Signals oder Ops) aus.

**Exit-Kriterium:** `docs/` oder internes Wiki: „Staging vs. Prod“ Tabelle; ein verantwortlicher Name für Staging-Betrieb.

**Score-Hebel:** +1,0 (größter Sprung für „Betrieb“).

---

### Schritt 3 — Secrets, Rotation, Keine-Leaks-Disziplin

**Ziel:** Kein Secret im Git; Rotation bei Rollenwechsel/Leck dokumentiert; `INTERNAL_API_KEY`, `OPENAI_API_KEY`, Gateway-JWT-Secrets, DB-Passwörter unter Kontrolle.

**Aktivitäten:**

- Abgleich mit `config/required_secrets_matrix.json` und `docs/SECRETS_MATRIX.md`.
- Pro Secret: **Wo liegt es?** (Vault/Manager) **Wer rotiert?** **Wie oft?**
- Dashboard: nur serverseitige `DASHBOARD_GATEWAY_AUTHORIZATION`, nie im Browser.

**Exit-Kriterium:** Unterschriebene oder im Ticket-System verankerte „Secret-Policy“ + einmalige Rotation üben (Dry-Run).

**Score-Hebel:** +0,5.

---

### Schritt 4 — SLOs und Messpunkte für die kritische Kette

**Ziel:** Zahlen, nicht Bauchgefühl: z. B. „Gateway `/ready` < 500 ms p95“, „Signal-Pipeline verzögert maximal X Minuten“, „LLM Operator-Explain p95 < Y s“ (realistisch wählen).

**Aktivitäten:**

- 5–10 **kritische** Endpunkte oder Jobs benennen.
- Prometheus/Grafana **oder** Monitor-Engine-Regeln nutzen; wo nichts existiert: mindestens **logbasierte** Checks + Zeitstempel in Runbook.
- Error-Budget-Idee: was passiert bei 3 Tagen Rot?

**Exit-Kriterium:** Einseitiges SLO-Dokument + erste Dashboards/Alerts mit **eindeutigen** Empfängern.

**Score-Hebel:** +0,5 bis +1,0.

---

### Schritt 5 — CI/CD: Merge nur bei grün + Release-Prozess

**Ziel:** `main` ist deploybar; kein manuelles „hoffentlich geht’s“.

**Aktivitäten:**

- `.github/workflows/ci.yml` (oder euer CI) als **Gate** vor Merge verbindlich machen.
- Build- und Deploy-Schritte für Gateway, Dashboard, ggf. Worker dokumentieren (`docs/release_build.md`).
- Versions-Tags oder Changelog für Releases.

**Exit-Kriterium:** Letzte 10 Builds grün **oder** dokumentierte Ausnahmen mit Ticket.

**Score-Hebel:** +0,5.

---

### Schritt 6 — Testpyramide schließen: E2E-Smoke (inkl. optional KI mit Fake)

**Ziel:** Eine **kurze** automatisierte Strecke: Browser oder API-only — „Dashboard kann Gateway erreichen“ + optional „Operator Explain mit Fake-Provider“.

**Aktivitäten:**

- Playwright (oder ähnlich) gegen Staging **oder** CI-Job mit Compose + Fake-LLM.
- Mindestens: Login/Session wie in eurem Produkt, Health-Seite, **ein** API-Call über BFF.
- KI: Orchestrator mit `LLM_USE_FAKE_PROVIDER=true` in Test-Compose.

**Exit-Kriterium:** Ein Job in CI oder nächtlicher Cron, der bei Rot **Slack/E-Mail** sendet.

**Score-Hebel:** +0,5.

---

### Schritt 7 — Launch-Dossier & Checkliste: formal abhaken

**Ziel:** `docs/LAUNCH_DOSSIER.md` und `docs/LaunchChecklist.md` sind **keine Deko**, sondern abgehakt mit Datum/Verantwortlichem.

**Aktivitäten:**

- Alle Punkte durchgehen, die für **eure** Jurisdiktion/Exchange gelten.
- Shadow-Modus, `RISK_ALLOWED_LEVERAGE_MAX`, Kill-Switch, Telegram/Broker-Freigaben explizit.

**Exit-Kriterium:** Sign-off (Product + Ops + ggf. Compliance).

**Score-Hebel:** +0,5 bis +1,0 (nur sinnvoll mit echtem Live-/Shadow-Wunsch).

---

### Schritt 8 — Shadow-Burn-in und evidenzbasierte Freigabe

**Ziel:** Live-Geld nur nach **messbarer** Stabilität in Shadow/Paper gemäß `docs/shadow_burn_in_ramp.md` (oder eurer angepassten Policy).

**Aktivitäten:**

- Definierte Dauer und KPIs (Drawdown-Events, Reconcile, Alert-Rate).
- Review-Meetings mit festem Protokoll.

**Exit-Kriterium:** Schriftliche Freigabe „Live Stufe 1“ mit Grenzen (Volumen, Symbole, Hebel).

**Score-Hebel:** +0,5 (nur relevant vor Live).

---

### Schritt 9 — Incident Response, Runbooks, Übungen

**Ziel:** Bei P1 reagiert niemand improvisiert ohne Netz.

**Aktivitäten:**

- Runbooks: Gateway down, DB full, Redis weg, Bitget API Fehler, LLM 502-Flut.
- On-Call-Rotation oder externer Dienst.
- **Game Day:** absichtlich einen Dienst stoppen und Zeit bis Recovery messen.

**Exit-Kriterium:** Protokoll einer Übung + aktualisierte Runbooks.

**Score-Hebel:** +0,5.

---

### Schritt 10 — Kontinuierlicher Betrieb: Review, Kosten, Roadmap

**Ziel:** 10/10 **halten** — Regression verhindern, Kosten der KI/API im Blick, technische Schuld budgetiert.

**Aktivitäten:**

- Quartals-Review: SLO-Report, Incident-Postmortems, Dependency-Updates.
- OpenAI/LLM: Budget, Rate-Limits, Missbrauchsszenarien.
- Roadmap: nur Features, die SLO nicht gefährden, oder SLO wird angepasst.

**Exit-Kriterium:** Wiederkehrender Kalendereintrag + Owner; `PRODUCT_STATUS.md` wird quartalsweise aktualisiert.

**Score-Hebel:** hält 10/10 stabil (ohne diesen Schritt driftet man zurück auf 7–8).

---

## Erwartete Score-Entwicklung (Richtwert)

| Nach Schritt | Typischer Gesamt-Score (Bandbreite)             |
| ------------ | ----------------------------------------------- |
| Ausgang      | 6,0 – 7,5                                       |
| 1–2          | 7,0 – 8,5                                       |
| 3–5          | 8,0 – 9,0                                       |
| 6–8          | 8,5 – 9,5                                       |
| 9–10         | 9,5 – **10,0** (nur mit Nachweis und Disziplin) |

**Hinweis:** Wenn ihr **kein Live-Trading** wollt, endet euer organisatorischer „10/10“ bei Paper/Shadow — das Repo bleibt **softwareseitig** trotzdem 10/10 faehig, ohne echte Börse anzufassen.

---

## Kurzfassung

- **P83-Stand:** **10/10** im Sinne des **vollstaendig gelieferten** Plattform-Repo (Doku + CI + Gaps P0).
- **Operativer** 10/10 (inkl. eurem ersten Live) = zusaetzlich Schritte 6–8 und Management-Signoff, nicht fehlendes Konstrukt.
- **Die zehn Schritte** bauen von reproduzierbarem Stack → Staging → Messung → CI/E2E → Launch/Burn-in → Ops-Kultur auf.

Dieses Dokument kann als Arbeitsvorlage dienen: jeden Schritt als Epic/Issue-Gruppe im Tracker abbilden und beim Exit-Kriterium abhaken.

---

## Prompt 10 — Abschluss (Software-Seite)

- **Release-Bericht:** `docs/PROMPT10_RELEASE_REPORT.md` (geänderte Dateien, Restrisiken, **Go/No-Go**-Logik, empfohlene Endtest-Reihenfolge).
- **Automatisiertes Gate:** `pnpm release:gate`, `pnpm dashboard:probe`, `pnpm e2e` (siehe `API_INTEGRATION_STATUS.md` §9).
- **Hinweis:** „100 % lauffähige Live-App“ im Sinne des Plans bedeutet **nachweisbare** grüne Ketten auf Ziel-Umgebung + Freigaben — nicht nur grüner Typecheck im Repo.
