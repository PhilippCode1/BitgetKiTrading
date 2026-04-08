# Lauf 49 — Onboarding, Hilfe, Vertrauenssprache (Produktabschluss)

Stand: 2026-04-05 (lokal verifiziert)

## Bezug zu Datei 07

Siehe [`07_ci_and_release_contract.md`](./07_ci_and_release_contract.md): Merge-/Release-Signale umfassen u. a. **`pnpm check-types`** (Dashboard + shared-ts) und im Compose-Job **Playwright** gegen `e2e/playwright.config.ts`. Dieser Lauf richtet die **kundennahe Oberfläche** aus; die technische Gate-Parität bleibt an 07 gebunden.

## Ziel

- **Ehrliche, verständliche** Erklärung von Paper, Shadow und Live sowie von **KI-Leistung und -Grenzen** — ohne leere Marketingfloskeln und ohne kalten Entwicklerton.
- **Geschlossenes Produktgefühl:** klare Einstiege (Welcome, Onboarding, Hilfe-Hub, Console-Home einfach), **HelpHint** dort, wo Orientierung fehlt, **ruhige Vertrauenstexte** (u. a. Konsole-Banner), **sinnvolle CTAs**.
- **Nachweise:** Screenshots zentraler Flächen + UI-/E2E-Checks.

## Geänderte bzw. relevante Artefakte (Überblick)

| Bereich                            | Quelle                                                                                                                        |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Welcome (Wertversprechen + Hilfe)  | `apps/dashboard/src/messages/de.json` / `en.json` → `welcome.*`, `help.welcome.*`; `WelcomeLanguageClient.tsx`                |
| Onboarding                         | `onboarding.*`, Steps `demo`, `ai`, `safety`                                                                                  |
| HelpHints Health / Paper           | `help.healthPage.*`, `help.paperPage.*`; Header in `console/health/page.tsx`, `console/paper/page.tsx`                        |
| Hilfe-Hub `/console/help`          | `pages.consoleHelp.*`, neu **`help.consoleHelpHub.*`**; `console/help/page.tsx` (Header mit `helpBriefKey` / `helpDetailKey`) |
| Account-Hub                        | `account.home.*`, `account.assistLayerLead`                                                                                   |
| Console-Einstieg einfach + KI-Pfad | `consoleHome.simple.*`, `consoleHome.kiPathBody`                                                                              |
| Konsole-Vertrauen                  | `console.trustBanner.*` → `ConsoleTrustBanner`                                                                                |
| Paper-Seite                        | `pages.paper.*` (Lead, Trust-Panel, Admin-`<details>`)                                                                        |
| Health / Safety-Diagnose (Copy)    | `pages.health.subtitle`, `pages.health.safetyDiagLead` (DE/EN)                                                                |
| E2E + Screens                      | `e2e/tests/trust-surfaces.spec.ts` → Ausgabe unter `docs/cursor_execution/49_trust_assets/`                                   |

## Visuelle Nachweise (Screenshots)

Nach erfolgreichem Lauf von `pnpm exec playwright test -c e2e/playwright.config.ts e2e/tests/trust-surfaces.spec.ts` (mit laufendem Dashboard unter `E2E_BASE_URL`, Standard `http://127.0.0.1:3000`):

| Datei                                       | Inhalt (Kurz)                                                                               |
| ------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `49_trust_assets/help-overview-desktop.png` | Hilfe & Überblick inkl. Kurzhilfe im Header                                                 |
| `49_trust_assets/health-entry-desktop.png`  | KI & Systemstatus — Einstieg + Hilfekontext                                                 |
| `49_trust_assets/paper-trust-desktop.png`   | Paper mit Lead- und Vertrauenspanel                                                         |
| `49_trust_assets/account-hub-desktop.png`   | Mein Konto — ruhiger Einstieg, Quick-Tiles                                                  |
| `49_trust_assets/welcome-gate.png`          | Sprach-Tor mit Paper/Shadow/Live-Lead (`welcome.valueLead`; UI-Sprache ohne Cookie ggf. EN) |
| `49_trust_assets/onboarding-de.png`         | Onboarding-Karte (sichtbarer Einstieg)                                                      |

Hinweis: `/welcome` ist in der Middleware vom Locale-Zwang **ausgenommen**; ohne Cookie kann die UI **EN** zeigen. Der Lead-Text enthält in **beiden** Sprachen „Paper“ — der E2E-Test prüft deshalb zweisprachig die Überschrift und den Paper-Bezug.

## Relevante UI-Prüfungen (ausgeführt)

| Prüfung                                                                                  | Ergebnis (lokal)                                                       |
| ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `pnpm check-types`                                                                       | **OK** (Turbo: `@bitget-btc-ai/dashboard`, `@bitget-btc-ai/shared-ts`) |
| `pnpm exec playwright test -c e2e/playwright.config.ts e2e/tests/trust-surfaces.spec.ts` | **6 passed** (nach `pnpm exec playwright install chromium`)            |

Voraussetzung E2E: Dashboard erreichbar, `globalSetup` kann Onboarding/Locale-Cookies für den authentifizierten Block setzen.

## E2E: Abdeckung der Einstiege

1. **Konsole (mit `storageState`):** `/console/help`, `/console/health`, `/console/paper`, `/console/account` — jeweils sichtbar: `main.dash-main`, `.console-trust-banner`, Screenshot.
2. **Ohne StorageState:** `/welcome` (Sprach-Tor + Produktkontext), `/onboarding` (Karte sichtbar).

## Finale Produktkopien (Deutsch, referenziert in `de.json`)

Die folgenden Texte sind die **kanonische** Kundenfassung in der App (Auszug; vollständige Keys im Repo).

### Welcome — Wertlead (`welcome.valueLead`)

> Du nutzt eine Plattform für Marktdaten, Signale und kontrollierte Ausführung: Paper ist die Übung ohne echte Börsenorders; Shadow beobachtet Entscheidungen oft parallel zur Live-Kette; Live bewegt echtes Kapital nur mit Freigaben und Richtlinien. KI fasst zusammen und beantwortet Fragen — sie ist keine Anlageberatung, platziert keine Orders im Hintergrund und ersetzt dein eigenes Risikomanagement nicht.

### Konsole — Vertrauensbanner (`console.trustBanner`)

- **strong:** Sensible Verbindungen laufen auf der Plattform — nicht in deinem Browser.
- **text:** API-Schlüssel und Admin-Funktionen bleiben serverseitig. Was du hier siehst, ist Status und Steuerung mit deiner Anmeldung — keine versteckten Orders durch die Oberfläche.

### Hilfe-Hub — Kurzhilfe (`help.consoleHelpHub`)

- **brief:** Kurze Wege zu Chart, Übung, KI-Fragen und Konto — ohne Menü zu durchsuchen.
- **detail:** Nutze die Liste wie ein Inhaltsverzeichnis. Paper bleibt Simulation; Signale und KI liefern Transparenz, keine Kaufempfehlung; System & Status zeigt, ob die Plattform Daten liefert, plus Assistent. Profi-Bereiche weiter über „Alle Funktionen (Pro)“.

### Health-Seite — Kurzhilfe (`help.healthPage`)

- **brief:** Dienstestatus, Alerts und der deutschsprachige Assistent — für Lagebild, nicht für stillschweigende Aktionen.
- **detail:** Hier siehst du, ob Datenpfade und Worker erreichbar sind und welche Monitor-Meldungen offen sind. Der Assistent beantwortet strukturierte Fragen serverseitig; es gibt keinen dauerhaften Chat, keine automatischen Orders und keine Änderung deiner Strategie aus dem Dialog. Paper bleibt Simulation; Shadow vergleicht oft Signale/Entscheidungen mit Live; echtes Geld bewegt nur der freigegebene Live-Pfad.

### Paper — Trust-Panel (`pages.paper.trustPanelTitle` / `trustPanelBody`)

- **Titel:** Paper, Shadow und Live — kurz erklärt
- **Body:** Paper: Übungstrades und Kontosimulation, keine Exchange-Orders. Shadow: häufig parallele Auswertung derselben oder ähnlicher Signale gegenüber dem Live-Pfad — nützlich für Abweichungen, aber kein zweites Orderbuch. Live: nur wenn dein Mandant und die Plattform-Freigaben es erlauben; Orders laufen serverseitig, nie mit API-Schlüsseln im Browser.

### Onboarding — Safety-Schritt (`onboarding.steps.safety.body`)

> Signale sind Systemeinschätzungen — keine Kaufempfehlung und kein garantierter Gewinn. KI und Assistenten ersetzen keine Anlageberatung. Paper schützt vor Echtgeld-Risiko; Live bleibt bewusst restriktiv. Cockpit und Konto zeigen, welche Pfade für dich freigeschaltet sind.

### Console-Home — KI-Pfad (`consoleHome.kiPathBody`)

> Unter „KI & Systemstatus“ beantwortet der Assistent Fragen auf Deutsch — frisch pro Anfrage, ohne dauerhaften Chat in dieser Oberfläche. Pro Signal gibt es auf der Detailseite Erklärungen und optional weitere KI-Schritte; das ersetzt keine Anlageberatung. Modell-Reports und Drift liegen unter Pro: Learning & Drift. Paper bleibt Übung; Live braucht weiterhin Freigaben.

### Account — Assistenz-Hinweis (`account.assistLayerLead`)

> Zwei getrennte Segmente für dein Konto (Einstieg vs. Abrechnung). Sie sind nicht dasselbe wie der Assistent unter „KI & Systemstatus“ — andere Registerkarten, andere Berechtigungen am Gateway. Antworten sind Orientierung: keine Trades, keine stillschweigenden Vertrags- oder Limitänderungen.

## Technische Korrektur in diesem Lauf

- **Hilfe-Seite:** `Header` unterstützt keine `titleRight`-Prop; Kurzhilfe erfolgt über **`helpBriefKey` / `helpDetailKey`** (wie auf Health/Paper), Import-Pfad zu `HelpHint` ist `@/components/help/HelpHint` (nur indirekt über `Header`).
- **E2E Welcome:** Assertion auf reines „Sprache“ bricht, wenn `/welcome` ohne Locale-Cookie **Englisch** rendert — Test prüft jetzt **zweisprachig** die Überschrift und weiterhin **Paper** im Karteninhalt.

## Bekannte offene Punkte

- **[FUTURE]** Weitere Flächen (z. B. einzelne Signal-Detail-Hilfen) können bei Bedarf mit demselben Muster (`helpBriefKey` / `helpDetailKey`) nachgezogen werden.
- **[RISK]** Screenshots unter `49_trust_assets/` können bei UI-Theme-Änderungen veralten — bei größeren Design-Passes E2E erneut ausführen.
- Playwright-Browser sind **nicht** immer vorinstalliert; CI/Neu-Clone: `pnpm e2e:install` bzw. `pnpm exec playwright install chromium`.

## Kurze Testanleitung

```powershell
Set-Location <repo-root>
pnpm check-types
# Dashboard + Gateway laufen, z. B. Port 3000:
pnpm exec playwright install chromium   # einmalig
pnpm exec playwright test -c e2e/playwright.config.ts e2e/tests/trust-surfaces.spec.ts
```

Screenshots erscheinen unter `docs/cursor_execution/49_trust_assets/`, sofern der Prozess Schreibrechte auf das Repo hat.
