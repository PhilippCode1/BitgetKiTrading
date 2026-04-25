# Main Console Information Architecture

Diese IA definiert die zentrale deutsche Hauptkonsole fuer `bitget-btc-ai`.
Sie gilt fuer private Owner-Nutzung durch Philipp Crljic und ersetzt keine
Risk-/Live-Gates.

## Zentrale Navigation

Die Main Console nutzt diese Hauptbereiche mit klaren deutschen Labels:

- Übersicht -> `/console`
- Bitget Assets -> `/console/market-universe`
- Signale & Strategien -> `/console/signals`
- Risk & Portfolio -> `/console/ops`
- Live-Broker -> `/console/live-broker`
- Sicherheitszentrale -> `/console/safety-center`
- Vorfälle & Warnungen -> `/console/incidents`
- Systemzustand & Datenflüsse -> `/console/system-health-map`
- Shadow & Evidence -> `/console/shadow-live`
- System Health -> `/console/health`
- Einstellungen -> `/console/account/language`
- Reports -> `/console/usage`
- Admin/Owner -> `/console/admin`

Technische Quelle der Primaernavigation:

- `apps/dashboard/src/lib/main-console/navigation.ts`
- gerendert ueber `apps/dashboard/src/components/layout/SidebarNav.tsx`

Leitregeln:

- Keine Customer-/Billing-/Sales-Navigation als Primärpfad.
- Jede Seite hat einen klaren Zweck, deutschen Titel und deutschen Empty State.
- Fehlertexte sind deutsch, handlungsorientiert und ohne interne Geheimnisse.
- Bei Backend-Ausfall bleibt die Konsole verständlich (deutliche Banner,
  degradierte Anzeige, nächste Schritte).

## Routen-Mapping

| Bereich | Hauptpfad | Unterseiten (aktuell relevant) | Zweck |
| --- | --- | --- | --- |
| Übersicht | `/console` | `-` | Gesamtstatus, Go/No-Go, wichtigste Blocker |
| Bitget Assets | `/console/market-universe` | `/console/capabilities`, `/console/no-trade` | Asset-Universe, Freigaben, Quarantine, Datenqualität |
| Signale & Strategien | `/console/signals` | `/console/signals/[id]`, `/console/strategies`, `/console/strategies/[id]`, `/console/learning`, `/console/news` | Signale, Strategiebezug, KI-Erklärung, No-Trade-Gründe |
| Risk & Portfolio | `/console/ops` | `/console/approvals`, `/console/paper` | Risk-Governor, Exposure, Drawdown, Freigaben |
| Live-Broker | `/console/live-broker` | `/console/live-broker/forensic/[id]`, `/console/safety-center`, `/console/incidents` | Orders, Reconcile, Safety-Latch, Kill-Switch, priorisierte Incidents |
| Shadow & Evidence | `/console/shadow-live` | `/console/usage` | Shadow-Burn-in, Performance-/Readiness-Spuren |
| System Health | `/console/health` | `/console/diagnostics`, `/console/self-healing`, `/console/terminal`, `/console/system-health-map` | Services, Provider, DB/Redis, Alert-Lage und Datenfluss-Landkarte |
| Einstellungen | `/console/account/language` | `/console/account/profile`, `/console/account/telegram` | Deutsche App-Einstellungen, Operatorprofil |
| Reports | `/console/usage` | `/console/news/[id]` | Scorecard-/Audit-/Drill-nahe Berichte |
| Admin/Owner | `/console/admin` | `/console/admin/rules`, `/console/admin/ai-governance` | Owner-spezifische Steuerung ohne Multi-Customer-Ziel |

## Konsolidierungsregeln

1. Legacy-Routen bleiben zunaechst bestehen, werden aber aus der primaeren
   Navigation entfernt und als `deprecated`/`out-of-scope` markiert.
2. Keine neue Navigationseintraege fuer Billing, Customer, Tenant, Pricing,
   Subscription, Checkout oder Payment.
3. `/portal/*` wird als Legacy-Bereich behandelt und nicht als Produktkern.
4. API/BFF-Routen werden in `operatorisch relevant` und `legacy commerce`
   getrennt dokumentiert.
5. Jede neue Main-Console-Seite braucht:
   - deutschen Seitentitel,
   - deutschen Empty State,
   - deutsche Fehlermeldung mit naechstem Schritt,
   - sichtbaren Bezug zu Go/No-Go oder Betriebskontext.

## Legacy-/Out-of-scope-Navigation

Diese Pfade sind nicht Teil der Ziel-IA und duerfen nicht ausgebaut werden:

- UI: Portal-Pfade (`/portal/...`), `/console/account/billing`,
  `/console/account/payments`, `/console/admin/billing`,
  `/console/admin/commerce-payments`, plus Kunden-Unterpfade unter
  `/console/admin/customers`
- API: Beispielpfad `/api/dashboard/commerce/customer/me`,
  plus `/api/dashboard/customer/portal-summary` und
  `/api/dashboard/admin/commerce-mutation`

Sie werden in Folgeprompts kontrolliert konsolidiert oder deaktiviert.
