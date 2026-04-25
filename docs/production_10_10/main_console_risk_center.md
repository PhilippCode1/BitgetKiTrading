# Main Console Risk Center

Status: implemented

## Zielbild

Das Risk-Modul der Main Console zeigt Multi-Asset-Risiko fuer Philipp in einer
deutschen Kontrollsicht. Fokus: Portfolio-Stress, Asset-Risikotier,
Live-Blocker und fail-closed Entscheidungsunterstuetzung.

## Sichtbare Bereiche

- Risk-Uebersicht:
  - Gesamtstatus (OK/Warnung/Blockiert)
  - Betriebsmodus
  - Daily/Weekly Loss
  - Drawdown
  - Margin Usage
  - offene Positionen/Kandidaten
  - Portfolio Exposure
  - groesste Einzelrisiken
- Asset-Risk-Tabelle:
  - Symbol, Risk Tier, Volatilitaet/ATR, Spread/Liquiditaet
  - Funding/OI (Futures)
  - Datenqualitaet
  - max erlaubter Modus
  - Blockgruende
- Portfolio-Risk:
  - Family Exposure
  - Direction Exposure
  - Cluster/Korrelation
  - Pending mirror trades
  - Open orders notional
  - Live block reasons

## Harte Live-Blocker (sichtbar)

- stale data
- no exchange truth
- safety latch
- kill switch
- margin exceeded
- max drawdown
- asset quarantined

## Fail-Closed

- Wenn Signal-/Risk-Snapshot fehlt, wird mindestens `stale data` als Blocker
  gesetzt.
- Kein Bereich zeigt implizit "Live frei", wenn Pflichtdaten unklar sind.

## Relevante Implementierung

- `apps/dashboard/src/app/(operator)/console/risk/page.tsx`
- `apps/dashboard/src/lib/risk-center-view-model.ts`
- `apps/dashboard/src/lib/main-console/navigation.ts`
