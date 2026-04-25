# Main Console Product Direction

Die Main Console ist die zentrale Arbeitsoberflaeche von `bitget-btc-ai`. Jede
neue UI-Arbeit muss diese Richtung staerken und darf keine parallele
Customer-, Billing-, Sales- oder Public-Marketing-Oberflaeche als Produktziel
aufbauen.

## Zielbild

- Die Main Console ist die zentrale Arbeitsoberflaeche fuer Philipp Crljic.
- Alle relevanten Features muessen dort logisch erreichbar sein.
- Navigation, Statusmeldungen, Warnungen, Freigaben und Hilfetexte muessen
  einfach, eindeutig und deutsch sein.
- Verstreute Seiten, alte Customer-/Billing-Flows und doppelte Operator-
  Ansichten muessen inventarisiert und spaeter konsolidiert werden.
- Die Main Console zeigt Go/No-Go klarer als Komfort- oder Demo-Funktionen.
- Die Bereiche Status, Assets, Signale, Risk, Live-Broker, KI-Erklaerung,
  Reports, Alerts, Settings und Go/No-Go sind als Kernumfang verbindlich.

## Pflichtbereiche der Main Console

Die Main Console muss mindestens diese Bereiche sichtbar oder erreichbar machen:

- Systemstatus, Runtime-Modus, Health und Readiness.
- Bitget-Assets, Instrumentenkatalog, Asset-Freigabe und Marktverfuegbarkeit.
- Ein eigenes Main-Console-Modul `Asset-Universum` mit Kennzahlen zu erkannt,
  aktiv, blockiert, quarantined, shadowfaehig und livefaehig.
- Ein eigenes Main-Console-Modul `Asset-Freigaben` mit Status "Live erlaubt",
  "Nur Shadow", "Nur Paper", "In Quarantaene", "Blockiert" und "Manuelle Pruefung noetig".
- Instrument-Panel mit Precision-/Order-Contract-Feldern (ProductType,
  MarginCoin, Tick Size, Lot Size, MinQty, MinNotional) und klaren
  Blockgruenden in Deutsch.
- Ein Modul `Datenqualitaet` pro Asset mit Candle-/Orderbook-/Funding-/OI-
  Status, letzter Aktualisierung und Live-Auswirkung.
- Ein Modul `Liquiditaet` pro Asset mit Spread, Orderbook-Frische,
  Slippage-Schaetzung, Liquiditaets-Tier, Live-Blockern und empfohlener
  Maximalgroesse.
- Ein Modul `Asset-Risk` pro Asset mit Risk-Tier, Leverage-Cap,
  Notional-Limit, Owner-Review-Pflicht und deutschen Blockgruenden.
- Ein Modul `Order-Sizing & Margin` pro Signal/Asset mit vorgeschlagener
  Groesse, max erlaubter Groesse, Risk-per-Trade, Margin-Nutzung,
  Leverage-Cap und Block-/Reduktionsgruenden.
- Ein Modul `Portfolio-Risiko` mit Gesamt-Exposure, Margin-Usage, offenen
  Positionen, Pending Orders/Candidates, Cluster-Risiko und Portfolio-Go/No-Go.
- Ein Modul `Strategie-Evidence` pro Asset/Asset-Klasse mit Strategie-ID,
  Version, Playbook, Evidence-Status, Scope-Match und deutschen Blockgruenden.
- Ein Modul `Live-Preflight` pro Live-Kandidat mit Pflicht-Gate-Status,
  fehlenden Gates, Block-/Warning-Gruenden und deutschem Hinweis
  "nicht handelbar, weil ...".
- Ein Modul `Sicherheitszentrale` als zentraler Kontrollraum fuer Kill-Switch,
  Safety-Latch, Reconcile, Exchange-Truth, Live-Pause und Emergency-Flatten.
- Ein Modul `Vorfälle & Warnungen` (Incident- und Alert-Ansicht) mit P0–P3,
  klarer Live-Block-Anzeige, Sortierung nach Kritikalität und ohne falsche
  Entwarnung bei fehlenden Daten.
- Ein Modul `Systemzustand & Datenflüsse` als Observability-Health-Landkarte
  mit Komponentenstatus, Frischebewertung, Live-Auswirkung und nächstem
  sicheren Schritt.
- Ein Modul `Order-Lifecycle & Exit` mit Order-State, Exchange-State,
  Unknown/Reconcile-Required, Reduce-only/Emergency-Status, Blockgruenden und
  letzter Aktion.
- Signale, Playbooks, KI-Erklaerungen und Entscheidungs-Lineage.
- Risk-Governor, Positionslimits, Exposure, Liquiditaet und Datenqualitaet.
- Paper-, Shadow- und Live-Broker-Status mit klarer Modustrennung.
- Reconcile, Exchange-Order-State, Kill-Switch und Safety-Latch.
- Reconcile-/Drift-Panel mit globalem Status, per-Asset-Status, offenen
  Drift-Faellen, Safety-Latch und deutschem Blockgrund.
- Alerts, Reports, Audit-Trail und Release-/Go-No-Go-Evidence.
- Settings fuer private Betreiberkonfiguration ohne echte Secrets im Browser.

## Navigationsprinzip

Die Navigation soll deutsch, kurz und handlungsorientiert sein. Jeder Bereich
muss erkennen lassen, ob er lesend, konfigurierend oder live-relevant ist.
Live-relevante Aktionen brauchen sichtbare Gate-Erklaerungen und duerfen ohne
vollstaendige Freigaben nicht ausfuehrbar sein.

## Konsolidierungsregel

Bestehende verstreute Seiten werden nicht blind geloescht. Zuerst ist ein
Inventar zu erstellen:

- Welche Seite existiert?
- Welchen Zweck erfuellt sie?
- Ist sie fuer Philipps private Main Console relevant?
- Welche Daten/API-Vertraege nutzt sie?
- Kann sie konsolidiert, als Legacy markiert oder entfernt werden?

Erst danach duerfen Routen, Komponenten oder Tests entfernt werden.

## Sprache

Die finale Anwendung ist deutsch. Neue UI-Texte muessen deutsch sein. Englische
Fachbegriffe sind nur erlaubt, wenn sie als etablierte technische Begriffe
notwendig sind und die Benutzerfuehrung trotzdem deutsch bleibt.
