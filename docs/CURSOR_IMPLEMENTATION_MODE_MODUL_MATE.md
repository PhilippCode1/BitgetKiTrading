# Umsetzungsmodus fuer Cursor (Modul Mate GmbH / bitget-btc-ai)

**Dokumentversion:** 1.0  
**Bezug:** Prompt 10; Regeln: `.cursor/rules/modul-mate-whole-file-delivery.mdc`  
**Code-Metadaten:** `shared_py.cursor_delivery_contract`

---

## Bauabschnitte (empfohlene Reihenfolge)

Das Repo enthaelt bereits Services (Gateway, Broker, LLM, …) und **fachliche Kontrakte** in `shared_py`
(Prompts 1–9). Die **Webapp-Schicht** (Kunde + Admin) und **persistente Geschaeftsdaten** folgen modular.

| BA       | Modul            | Ziel                            | Typische Artefakte                                              |
| -------- | ---------------- | ------------------------------- | --------------------------------------------------------------- |
| **BA00** | Kontrakte & Doku | Kanonische Policies             | `shared_py/*_contract.py`, `docs/*_MODUL_MATE.md`               |
| **BA01** | Datenmodell DB   | Kunden, Abo, Vertrag, Audit     | `infra/migrations/postgres/*.sql`, optionale ORM-Modelle        |
| **BA02** | Auth & Session   | Login, Rollen, Philipp-Admin    | Gateway-Routes, JWT/Session, MFA                                |
| **BA03** | Kunden-API       | Lifecycle, Gates, read APIs     | `services/api-gateway` oder neuer `services/customer-api`       |
| **BA04** | Admin-API        | Freigaben, KI-Schalter, Notfall | geschuetzte Routes, Audit-Append                                |
| **BA05** | Zahlungen        | PSP, Webhooks, Rechnungen       | Integrations-Service, idempotente Handler                       |
| **BA06** | Trading-Gates    | Demo/Live strikt                | Erweiterung `live-broker` / Gateway-Guards mit `product_policy` |
| **BA07** | KI-Anbindung     | Registry, Traces                | `llm-orchestrator` + `ai_layer_contract`                        |
| **BA08** | Telegram         | notify → optional OTP           | Bot-Service, Webhook, keine Secrets in Logs                     |
| **BA09** | Frontend Kunde   | `/app`                          | SPA/SSR nach Stapel unten                                       |
| **BA10** | Frontend Admin   | `/verwaltung`                   | Admin-UI, strikte Auth                                          |
| **BA11** | E2E & Haertung   | Tests, Observability            | Playwright/pytest, Alerts                                       |

**Hinweis:** BA00 ist fuer Modul-Mate-Vertraege **weitgehend erledigt**; neue Arbeit startet sinnvoll bei **BA01** oder **BA09**, je nach Prioritaet API-first vs. UI-first.

---

## Dateipaket-Regeln

- Pro Cursor-Antwort: **nur vollstaendige Dateien** — keine Auslassungen (`// ...`), keine „Rest unveraendert“.
- Wenn eine Datei > ca. 300 Zeilen: **eine Datei pro Chat-Block**, vollstaendig; bei Bedarf **zwei aufeinanderfolgende** Nachrichten.
- **Neue** Dateien: kompletter Inhalt. **Geaenderte** Dateien: **gesamte** neue Dateiversion.
- Konfigurationsdateien (`.env.example`) ohne echte Secrets.

---

## Antwortstandard (festes Format)

Jede umsetzungsrelevante Cursor-Antwort soll diese Abschnitte haben (Reihenfolge):

1. **Ziel des Schritts** — ein Satz.
2. **Betroffene Dateien** — Liste mit Pfaden.
3. **Vollstaendige Dateien** — pro Datei: `Pfad` dann Code-Fence mit **gesamtem** Inhalt.
4. **Kurze Testanleitung** — Befehle oder manuelle Schritte.
5. **Bekannte offene Punkte** — nummeriert oder Aufzaehlung.

Siehe Konstanten `RESPONSE_SECTION_TITLES_DE` in `cursor_delivery_contract.py`.

---

## Qualitaetsregeln

- **Keine** Teil-Snippets als Ersatz fuer ganze Dateien.
- **Keine** Platzhalter wie „hier spaeter …“ im Produktionscode (in Doku mit `[PROVISIONAL]` ok).
- Tests oder Linter nach Aenderung **ausfuehren** wenn moeglich.
- Offene Punkte **explizit** benennen statt zu verschweigen.

---

## Unsicherheit: Vorgehen

1. **Annahmenliste** (kurz, nummeriert).
2. **Standardentscheidung** pro Annahme (eine Zeile).
3. **Ganze Dateien** liefern.
4. Offene Punkte im Abschnitt „Bekannte offene Punkte“ wiederholen.

---

## Kennzeichnung von Schulden und Risiken

Im Code oder in Commit-Texten **sparsam** und einheitlich:

| Marker             | Bedeutung                            |
| ------------------ | ------------------------------------ |
| `[TECHNICAL_DEBT]` | Bewusst verschobene Refaktorierung   |
| `[PROVISIONAL]`    | Temporaer, muss ersetzt werden       |
| `[RISK]`           | Bekanntes Produkt-/Sicherheitsrisiko |
| `[FUTURE]`         | Geplante Erweiterung, nicht v1       |

Konstanten: `DELIVERY_MARKER_*` in `cursor_delivery_contract.py`.

---

## Versionen: v1, v2, Ausbau

### Version 1 (MVP kommerziell vertretbar)

- Kunde: Registrierung, E-Mail, Probephase, Demo-Trading, Vereinbarung anzeigen/annehmen, Abo-Zahlung **eine** PSP-Methode, Echtgeld **nach** Admin-Freigabe, Basis-Audit.
- Admin: Philipp-only, Kundenliste, Live-Freigabe, Notfall-Stopp, Lesen von Zahlungsstatus.
- KI: bestehender Orchestrator, strukturierte Antworten, **kein** autonomes Live-Trading ohne Bestaetigung.

### Version 2

- Mehr Zahlarten (PayPal, Wallets …), Mahnwesen, Gewinnbeteiligungs-Abrechnung UI, Telegram OTP, Canary-Modell-Rollouts.

### Spaeter

- Multi-Exchange, erweiterte RAG, Mobile Apps, Dark Mode, weitere Sprachen.

---

## Startstruktur & Technologie-Stapel (Zielbild Webapp)

### Aktueller Kern (Repo)

- **Sprache:** Python 3.11+
- **API:** FastAPI / Starlette (Gateway)
- **Daten:** PostgreSQL, Redis
- **Broker:** `live-broker`, `paper-broker`
- **KI:** `llm-orchestrator`, OpenAI-kompatibel
- **Kontrakte:** `shared_py`, JSON-Schemas unter `shared/contracts`

### Empfohlene Ergaenzung fuer professionelle Web-Oberflaeche

| Schicht                | Empfehlung [ANNAHME]                                                                                                    |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Frontend Kunde + Admin | **Next.js** (App Router) **oder** **Remix** — SSR, i18n-ready, eine Codebasis mit Route-Groups `(customer)` / `(admin)` |
| Styling                | **Tailwind CSS** + Design-Tokens aus `design_system_contract`                                                           |
| Auth Browser           | BFF-Cookies oder kurzlebige Tokens; **keine** langen Refresh-Tokens im localStorage ohne Konzept                        |
| Secrets                | Vault/KMS; Keys nie im Frontend                                                                                         |
| Zahlungen              | **Stripe** oder PSP mit **SEPA + Wallets** — Webhooks idempotent                                                        |
| Deploy                 | Container (Docker), CI mit Tests                                                                                        |

### Ordnerstruktur (Ziel, parallel zu `services/`)

```
services/              # bestehend
shared/python/         # bestehend
shared/contracts/      # bestehend
infra/                 # bestehend
web/                   # NEU optional: Next.js Monolith Kunde+Admin
  apps/
    customer/          # oder ein App mit route groups
    admin/
  packages/ui/         # gemeinsame Komponenten + Tokens
docs/                  # Produkt- & Umsetzungsdocs
.cursor/rules/         # Cursor Lieferregeln
```

**Alternative:** ein einziges `web/` mit `src/app/(konto)` und `src/app/(verwaltung)` statt zwei Apps — weniger Duplikat.

---

## Praxis-Hinweis

Nach jeder Antwort pruefen: **Offene Punkte genannt?** **Dateien vollstaendig?** Die Cursor-Regel **alwaysApply** unterstuetzt das dauerhaft.
