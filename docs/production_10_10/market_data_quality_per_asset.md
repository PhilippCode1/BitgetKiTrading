# Market Data Quality Per Asset

## 1) Zielbild

Jedes Bitget-Asset wird datenqualitativ bewertet. Ohne frische, plausible und
vollstaendige Marktdaten bleibt Live-Trading fail-closed blockiert.

## 2) Datenquellen

- Candles/Klines
- Orderbook/Top-of-Book
- Funding (Futures)
- Open Interest (falls Strategie es nutzt)
- Instrument-Metadaten/Katalog
- Redis/Eventbus-Freshness und Signal-Input-Vollstaendigkeit

## 3) Qualitaetskriterien

Mindestens:

1. Candles vorhanden
2. keine kritischen Candle-Luecken
3. keine out-of-order Candles
4. plausible OHLC-Werte
5. plausibles Volumen
6. Orderbook vorhanden
7. Orderbook fresh
8. Spread plausibel
9. Top-of-Book plausibel
10. Funding fresh bei Futures
11. OI fresh bei Futures, falls genutzt
12. Instrument-Metadaten fresh
13. MarketFamily eindeutig
14. ProductType eindeutig
15. Delisting/Suspension nicht aktiv
16. niedrige Provider-Fehlerquote
17. Redis/Eventbus-Freshness ausreichend
18. Signal-Input vollstaendig

## 4) Statuswerte

- `data_unknown`
- `data_ok`
- `data_warning`
- `data_stale`
- `data_incomplete`
- `data_invalid`
- `data_provider_error`
- `data_quarantined`
- `data_live_blocked`

## 5) Quarantaene-Regeln

Quarantaene ist explizit (`data_quarantined`) und blockiert Live sofort.
Aufhebung erst nach reproduzierbarer Datenpruefung und dokumentierter Ursache.

## 6) Delisting/Suspension-Regeln

`delisted` oder `suspended` blockieren Live sofort (`data_live_blocked`), ohne
Fallback auf alte Datenannahmen.

## 7) Live-Blocker

- `data_unknown`, `data_stale`, `data_incomplete`, `data_invalid`,
  `data_provider_error`, `data_quarantined`, `data_live_blocked`
- fehlendes/stales Orderbook
- extremer Spread
- Delisting/Suspension
- Futures-Funding stale: mindestens Warning, je Strategie ein Blocker

## 8) Main-Console-Anzeige

Pro Asset sichtbar:

- Asset
- Status
- letzte Aktualisierung
- Candle-Qualitaet
- Orderbook-Qualitaet
- Funding/OI-Status
- Blockgruende
- Live-Auswirkung (`LIVE_BLOCKED` vs `LIVE_ALLOWED`)

## 9) Asset-Report

`scripts/market_data_quality_report.py` erzeugt Asset-Reports mit:

- Datum/Zeit
- Git SHA
- Asset/Symbol
- MarketFamily
- ProductType
- Datenquelle
- Quality Status
- Block Reasons
- Warnings
- Live-Auswirkung
- PASS/PASS_WITH_WARNINGS/FAIL

## 10) Tests

```bash
python scripts/market_data_quality_report.py --dry-run
python scripts/market_data_quality_report.py --input-json tests/fixtures/market_data_quality_sample.json --output-md reports/market_data_quality_sample.md --output-json reports/market_data_quality_sample.json
pytest tests/data/test_market_data_quality.py -q
pytest tests/security/test_market_data_quality_live_blocking.py -q
pytest tests/scripts/test_market_data_quality_report.py -q
pytest tests/tools/test_check_market_data_quality.py -q
```

## 11) No-Go-Regeln

- Kein Live ohne Datenqualitaetsgate.
- Kein Ignorieren von stale/invalid/incomplete Daten.
- Kein stilles Freischalten bei Delisting/Suspension.
- Keine Behauptung, dass alle Assets ohne Datenpruefung livefaehig sind.
