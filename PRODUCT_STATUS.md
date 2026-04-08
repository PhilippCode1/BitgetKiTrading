# Produktstatus (ehrliche Übersicht)

Stand: Abschlussrunde Prompt 10 — konsolidierter Ist-Zustand des Monorepos **ohne** Marketing-Aufschlag.

---

## 1. Was jetzt wirklich funktioniert

- **Trading-/Markt-Pipeline (Kern):** Architektur und Doku beschreiben eine produktionsnahe Kette (Marktdaten → Engines → Signale → Paper/Shadow/Live über Live-Broker). Konkreter Lauf hängt von **laufenden Diensten, ENV, Bitget-Zugang und DB/Redis** ab — siehe `docs/LOCAL_START_MINIMUM.md`, `README.md`.
- **API-Gateway:** Zentrale HTTP-Schicht mit Auth, Rate-Limits, viele proxied Lesepfade; **zwei KI-Routen** für das Dashboard: `POST /v1/llm/operator/explain` und `POST /v1/llm/operator/strategy-signal-explain` (jeweils Forward mit `INTERNAL_API_KEY` zum LLM-Orchestrator, siehe `ai-architecture.md`).
- **LLM-Orchestrator:** Echter Dienst mit Structured Output, Retrieval, Cache; **Operator Explain** und **Strategie-Signal-Erklaerung** (`/llm/analyst/operator_explain`, `/llm/analyst/strategy_signal_explain`). **OpenAI** nur mit gesetztem `OPENAI_API_KEY`; für Tests `LLM_USE_FAKE_PROVIDER=true`.
- **Dashboard:** Zwei KI-Arbeitsfunktionen: Operator-Assistent auf **`/console/health`** (BFF `operator-explain`) und Strategie-Signal-Panel auf **Signaldetail** (`strategy-signal-explain`); Fehler-/Lade-UX wie beim ersten Pfad. Siehe `qa-report.md` (QA fokussiert Operator Explain).
- **Automatisierte Tests (Auszug):** `tests/unit/api_gateway/test_routes_llm_operator.py`, `tests/llm_orchestrator/test_structured_fake_provider.py`, Dashboard-Jest u. a. `operator-explain-errors`, `strategy-signal-explain-errors`. **Playwright:** `e2e/tests/release-gate.spec.ts` (lokal mit `pnpm e2e`, in CI im Job `compose_healthcheck`) prüft u. a. Startseite, Konsole, Terminal/Chart, BFF Operator-Explain und Broker — kein Ersatz für manuelles Staging-Review aller Screens.

---

## 2. Was noch offen oder technisch blockiert ist

- **Voller Produktionsbetrieb:** Hängt von Secrets, Netzwerk, Exchange, Compliance und organisatorischen Freigaben ab — siehe `docs/LAUNCH_DOSSIER.md`, `docs/LaunchChecklist.md`; dieses Repo liefert **Software + Doku**, keine automatische „Go-Live-Garantie“.
- **KI jenseits der zwei Dashboard-Pfade:** Weitere Orchestrator-Endpunkte (Hypothesen, News-Summary, …) sind **nicht** alle als Gateway+Dashboard-BFF für Endnutzer angebunden; News-Engine o. Ä. nutzt LLM separat Dienst-zu-Dienst.
- **Persistenter Chat / Multi-Turn:** Bewusst **nicht** gebaut; keine serverseitige Konversationshistorie für den Operator-Assistenten.
- **CI-Umfeld:** Gateway-Unit-Tests mit vollem `create_app()` brauchen konsistente Pflicht-ENV (Secrets-Matrix); lokal ohne gesetzte Variablen können einzelne Suites fehlschlagen — `test_routes_llm_operator.py` setzt die nötigen Keys für sich.
- **Einzelne Doku-Dateien** unter `docs/` können ältere Formulierungen enthalten; **Quelle der Wahrheit für die gebaute KI-Strecke:** `ai-architecture.md` + `release-readiness.md`.

---

## 3. Was als Nächstes sinnvoll wäre (Skalierung Produkt)

1. **Weitere KI-Funktionen nur mit klarem Scope:** jeweils Gateway+BFF+Schema+UI (kein generischer Chat), `execution_authority`-Policy im Schema.
2. **E2E-Test (Playwright):** Kernpfade sind angebunden (`pnpm release:gate:full`, CI `compose_healthcheck`); bei neuen Oberflächen Selektoren/Specs erweitern.
3. **Observability:** Metriken/Latenz für `llm_operator_explain` am Gateway und im Orchestrator, Dashboard nur aggregierte Ops-Sicht.
4. **Kosten/Quoten:** pro Tenant oder global Limits, falls kommerzielle Nutzung wächst.
5. **Redaktionelle Konsistenz:** Onboarding/Landing bei jedem neuen sichtbaren KI-Feature anpassen (vermeidet „versprochen, aber nicht im Menü“).

---

## Verwandte Dateien

| Datei                       | Zweck                                                             |
| --------------------------- | ----------------------------------------------------------------- |
| `FINAL_READINESS_REPORT.md` | Ehrliche Endbewertung Reifegrad je Bereich, Gesamtscore, Restplan |
| `ai-architecture.md`        | Technischer KI-Datenfluss, Konfiguration, manueller Test          |
| `release-readiness.md`      | Setup, Tests, offene Punkte, nächster Produktionsschritt          |
| `qa-report.md`              | Qualitätsdurchgang Operator-Explain                               |
