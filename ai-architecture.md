# KI-Architektur (Ist-Stand)

Dieses Dokument beschreibt, **was im Monorepo wirklich angebunden ist** und was bewusst **nicht** als „Chat-KI“ verkauft wird.

## Komponenten

| Schicht                                                   | Rolle                                                                                                                                                                                                             |
| --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **LLM-Orchestrator** (`services/llm-orchestrator`)        | Einziger Dienst mit OpenAI (oder `LLM_USE_FAKE_PROVIDER` für Tests). Structured Output, RAG-Retrieval, Redis-Cache, Circuit Breaker. Alle `/llm/*`-Pfade verlangen `X-Internal-Service-Key` (`INTERNAL_API_KEY`). |
| **API-Gateway**                                           | Öffentliche HTTP-Schicht für das Dashboard (JWT `gateway:read` / sensibles Auth). Leitet Operator-KI **serverseitig** zum Orchestrator weiter — **kein** OpenAI-Key im Browser oder im Dashboard-Container nötig. |
| **Dashboard BFF** (`apps/dashboard` → `/api/dashboard/*`) | Next.js-Server: trägt `DASHBOARD_GATEWAY_AUTHORIZATION` (Bearer-JWT) zum Gateway.                                                                                                                                 |
| **Dashboard-UI**                                          | Operator-Assistent auf **Health** (`/console/health`) und **Strategie-Signal-KI** auf **Signaldetail** (`/console/signals/[id]`); nur BFF-Routen, **keine** lokale Antwort-Attrappe.                              |

## Erste echte End-to-End-Funktion: Operator-Erklärung

### Eingabe (Nutzer)

- Pflicht: `question_de` (Deutsch, 3–8000 Zeichen).
- Optional: `readonly_context_json` (JSON-Objekt), z. B. Ausschnitte aus Health/Signalen — **nur** Prompt-Kontext, **keine** serverseitige Speicherung als Verlauf.

### Verarbeitung

1. Browser → `POST /api/dashboard/llm/operator-explain` (JSON).
2. BFF prüft `DASHBOARD_GATEWAY_AUTHORIZATION`, forwarded zu `POST /v1/llm/operator/explain`.
3. Gateway: `require_sensitive_auth`, Audit-Action `llm_operator_explain` (u. a. `question_len`), Forward mit `INTERNAL_API_KEY` → Orchestrator `POST /llm/analyst/operator_explain`.

### Modellaufruf & Prompt-Logik

- Implementiert im Orchestrator (`run_operator_explain`): Retrieval-Tags `operator_explain`, festes JSON-Schema `operator_explain.schema.json` (`execution_authority` immer `none`).

### Antwortformat (Orchestrator → UI)

Typisches Envelope (Auszug): `ok`, `provider`, `result` (Felder u. a. `explanation_de`, `referenced_artifacts_de`, `non_authoritative_note_de`), `provenance`.

### Fehlerbehandlung

- **503** (BFF): fehlendes Dashboard-Gateway-JWT.
- **503** (Gateway): fehlende Basis-URL (`LLM_ORCH_BASE_URL` oder ableitbar aus `HEALTH_URL_LLM_ORCHESTRATOR`) oder fehlendes `INTERNAL_API_KEY`.
- **401** (Gateway): keine Berechtigung für sensible Reads.
- **413 / 422 / 502**: vom Orchestrator bzw. Upstream (Gateway reicht strukturierte Fehler weiter).
- **Timeouts**: BFF/Gateway ~125 s / 120 s — LLM kann langsam sein.

### Verlauf & Speicher

- **Kein** persistenter Chat-Verlauf für diese Funktion: jede Anfrage ist stateless (abgesehen von Orchestrator-internem Cache/Provenance nach bestehendem LLM-Service).

### Konfiguration (Gateway)

- `INTERNAL_API_KEY`: muss mit dem Orchestrator übereinstimmen.
- `LLM_ORCH_BASE_URL` **oder** `HEALTH_URL_LLM_ORCHESTRATOR` (Basis-URL wird aus Scheme/Host/Port der Health-URL abgeleitet, wenn `LLM_ORCH_BASE_URL` leer ist).

### Zweite End-to-End-Funktion: Strategie-/Signalerklärung

1. Browser → `POST /api/dashboard/llm/strategy-signal-explain` mit `signal_context_json` (+ optional `focus_question_de`).
2. Gateway: `POST /v1/llm/operator/strategy-signal-explain`, Audit `llm_operator_strategy_signal_explain`, Forward → Orchestrator `POST /llm/analyst/strategy_signal_explain`.
3. Schema `strategy_signal_explain.schema.json`, Task-Type / Provenance `strategy_signal_explain`, `execution_authority` fest `none`.

### Transparenz: „KI“ im Produkttext

- **Direkter LLM-Aufruf aus dem Dashboard:** Health (**Operator Explain**) und **Signaldetail** (**Strategie-Signal-Erklaerung**).
- **„AI insights“ ohne diese Formulare:** Lern-/Drift-Reports, deterministischer Signal-Kontext auf derselben Seite, News-Scoring über andere Pfade (DB/Redis/Engines, teils interner LLM-Einsatz). Statischer Text ohne Backend = **kein** LLM.

## Was die KI **noch nicht** tut

- Kein freies Multi-Turn-Chat-UI über alle Themen.
- Keine automatischen Trades oder Freigaben aus diesem Endpunkt (`execution_authority` ist schemafest `none`).
- Weitere Orchestrator-Endpunkte (Hypothesen, News-Summary, …) ohne dedizierte Gateway+BFF-Kette — viele nur intern Dienst-zu-Dienst (z. B. News-Engine).

## Fake-Provider

Mit `LLM_USE_FAKE_PROVIDER=true` liefert der Orchestrator deterministische Testantworten — **nur** für lokale Tests/CI, nicht als Produktionsersatz (Validation in `config/settings.py`).

---

## Lokaler End-to-End-Test (Klicks)

Voraussetzungen: Stack läuft (z. B. `pnpm stack:local` oder `docker compose up`), **API-Gateway** erreichbar, **LLM-Orchestrator** läuft, in `.env.local` des Dashboards mindestens `API_GATEWAY_URL` (oder `NEXT_PUBLIC_API_BASE_URL`) und **`DASHBOARD_GATEWAY_AUTHORIZATION`** (Bearer-JWT mit `gateway:read`, siehe `scripts/mint_dashboard_gateway_jwt.py`). Im **Gateway** müssen **`INTERNAL_API_KEY`** (gleicher Wert wie beim Orchestrator) und **`HEALTH_URL_LLM_ORCHESTRATOR`** oder **`LLM_ORCH_BASE_URL`** gesetzt sein. Für echte OpenAI-Antworten: Orchestrator-ENV **`OPENAI_API_KEY`** und **`LLM_USE_FAKE_PROVIDER=false`**. Ohne Key zeigt die Strecke einen **ehrlichen** Fehler (z. B. „OpenAI: OPENAI_API_KEY fehlt“ über 502).

### Klicks im Browser

1. Dashboard starten: `pnpm dev` im Ordner `apps/dashboard` (nach ENV-Änderung neu starten).
2. Anmelden / zur **Konsole** wechseln (wie in eurem Setup vorgesehen).
3. Im linken Menü **„Health & incidents“** / **„System & Status“** öffnen (`/console/health`).
4. Nach unten scrollen bis zum Panel **„Operator assistant (real LLM)“** / **„Operator-Assistent (echtes LLM)“**.
5. Im Feld **Frage** mindestens drei Zeichen eingeben, z. B. `Was bedeutet Live-Gate in diesem System?`
6. Optional: im JSON-Feld einen kleinen Kontext einfügen, z. B. `{}` oder `{"symbol":"BTCUSDT"}` — oder leer lassen.
7. **„Get explanation“** / **„Erklaerung holen“** klicken — warten (bis ca. 2 Minuten möglich); der Button zeigt den Ladezustand, der Bereich ist per `aria-busy` markiert.
8. Erwartung bei Erfolg: Text unter **Erklärung**, ggf. **Referenzen**, **Hinweis**, **Provider**, **Task type (provenance)**.
9. **Wiederholung:** **„Run again (same input)“** / **„Nochmal ausfuehren“** klicken oder Frage leicht ändern und erneut absenden. Nach einem Fehler: **„Retry“** / **„Erneut versuchen“**.

**Signaldetail (zweite KI-Strecke):** Konsole → **Signale** → ein Signal öffnen → Panel **„KI: Strategie- und Signalerklaerung“** → **„Erklaerung anfordern“** (optional Fokusfrage). Erwartung wie oben: strukturierte Felder, bei Fake gelber Hinweis.

### Automatisierte Tests (ohne Browser)

- **Gateway (Forward gemockt):** vom Repo-Root  
  `python -m pytest tests/unit/api_gateway/test_routes_llm_operator.py -q`
- **Dashboard (Fehlertext & HTTP-Mapping):**  
  `cd apps/dashboard && pnpm test -- src/lib/__tests__/api-error-detail.test.ts src/lib/__tests__/operator-explain-errors.test.ts src/lib/__tests__/strategy-signal-explain-errors.test.ts --runInBand`

## Siehe auch

- **`PRODUCT_STATUS.md`** — Lieferstatus (was geht / offen / nächste Schritte)
- **`release-readiness.md`** — Setup, Testkommandos, nächster produktiver Schritt
- **`qa-report.md`** — Qualitätsdurchgang Operator-Explain (UX, Edge Cases)
