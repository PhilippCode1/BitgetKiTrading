# Main Console Chart-Arbeitsplatz

Status: implemented

## Zielbild

Der Chart-Arbeitsplatz in der Main Console ist eine deutsche Multi-Asset-Analyseflaeche.
Er dient der Sichtbarkeit, Signalbewertung und Risikoentscheidung. Er fuehrt keine
Live-Order per Standard aus.

## Funktionsumfang

- Asset-Auswahl aus der kombinierten Symbolmenge (Asset-Universum + Watchlist).
- Timeframe-Auswahl (`1m`, `5m`, `15m`, `1h`, `4h`).
- Datenfrische-Status inklusive kritischer Marktluecken.
- Anzeige von Market-Family, ProductType, Risk-Status.
- Signal-Overlay im Chart und Signalpanel fuer Begruendung/Risk-Hinweise.
- Liquiditaets-/Spread-Hinweise und Datenqualitaets-Hinweis.
- Leerer Datenzustand mit klarer deutscher Handlungsanleitung.

## Sicherheits- und Fail-Closed-Regeln

- Keine aktive Orderausfuehrung im Chart-Modul.
- Wenn Kerzen fehlen: `Keine Marktdaten verfuegbar, Live blockiert.`
- Wenn Daten veraltet: `Daten veraltet, keine Live-Freigabe.`
- Wenn Asset blockiert/quarantaene: `Asset in Quarantaene.`
- Wenn Datenquelle nicht erreichbar: `Bitget-Datenquelle nicht erreichbar.`
- Fehlerdetails werden gekuerzt und einfache Secret-Marker werden maskiert.

## Offene externe Abhaengigkeiten

- Vollstaendige Asset-Metadaten (inkl. ProductType/Quarantaene) haengen von der
  Gateway- bzw. Bitget-Integration ab.
- Candle-/Orderbook-Vollabdeckung fuer jedes Bitget-Asset ist extern abzusichern.

## Verifikation

- Jest-Tests fuer Alert-Logik, Datenfrische-/Empty-State-Texte und Error-Redaction:
  `apps/dashboard/src/lib/__tests__/chart-workspace-status.test.ts`
- Bestehende Terminal-/Live-Daten-Tests bleiben aktiv.
