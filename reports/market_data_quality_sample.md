# Market Data Qualitaetsreport

- Datum/Zeit: `2026-04-25T17:18:15.176534+00:00`
- Git SHA: `a51df1e`
- Anzahl gepruefter Assets: `2`

## PASS/WARN/FAIL/UNKNOWN pro Asset

- `BTCUSDT`: `PASS`
- `ALTUSDT`: `FAIL`

## Haeufigste Datenfehler

- `candle_critical_gap`: `1`
- `orderbook_stale`: `1`
- `top_of_book_missing`: `1`
- `funding_missing`: `1`
- `open_interest_missing`: `1`

## Live-Blocker

- `ALTUSDT`

## Naechste Schritte

- Echte Bitget-Read-only-Datenqualitaetslaeufe fuer alle aktiven Assets durchführen.
- Fail/Unknown Assets in Main Console 'Datenqualitaet' priorisiert anzeigen.
- Funding/OI-Warnungen fuer strategie-relevante Assets zu Blockern hochstufen.

## Deutsche Zusammenfassung fuer Philipp

- Asset BTCUSDT: Datenqualitaet PASS, Live-Auswirkung LIVE_ALLOWED, Blockgruende: keine, Warnungen: keine
- Asset ALTUSDT: Datenqualitaet FAIL, Live-Auswirkung LIVE_BLOCKED, Blockgruende: candle_critical_gap, orderbook_stale, top_of_book_missing, funding_missing, open_interest_missing, Warnungen: keine