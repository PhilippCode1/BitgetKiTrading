# Market Data Runtime Evidence Guide

Diese Anleitung beschreibt, wie Philipp echte Runtime-Evidence fuer `market_data_quality_per_asset` erzeugt, ohne Live-Trades auszufuehren.

## 1) Welche Services laufen muessen

- `market-stream` (Ticker/Orderbook-Ingestion)
- `feature-engine` (Qualitaets-/Staleness-Signale)
- `signal-engine` (Quality-Gate und Audit-Felder)
- `live-broker` im fail-closed Modus (kein echtes Trading)
- Redis/Postgres fuer Frische- und Persistenzpruefung

## 2) Welche ENV noetig ist

- `EXECUTION_MODE=paper` oder `EXECUTION_MODE=shadow` (nicht `live`)
- `LIVE_TRADE_ENABLE=false`
- `LIVE_BROKER_ENABLED=true` nur fuer Preflight/Blocking-Nachweis
- Bitget Read-only ENV fuer Exchange-Truth-Vergleich (keine Write-Rechte)
- Marktdatengrenzen gesetzt (Orderbook/Ticker/Funding-Freshness, Gap-Schwellen)

## 3) Wie lange Daten gesammelt werden sollen

- Mindestens 60 Minuten pro Asset-Familie (spot, margin, futures)
- Bei Futures zusaetzlich mindestens ein Funding-Fenster erfassen
- Bei Stoerungen: Fenster neu starten und Incident markieren

## 4) Welche Assets geprueft werden

- BTCUSDT (futures), ETHUSDT (futures)
- mindestens ein Spot-Asset und ein Margin-Asset
- alle produktiv vorgesehenen Assets aus Asset-Universe

## 5) Welche Kommandos auszufuehren sind

```bash
python scripts/asset_data_quality_report.py --output-md reports/asset_data_quality.md --output-json reports/asset_data_quality.json
python tools/check_market_data_quality.py --report reports/asset_data_quality.json
python tools/check_market_data_quality.py --report reports/asset_data_quality.json --strict-live
```

## 6) Welche Reports entstehen

- `reports/asset_data_quality.md`
- `reports/asset_data_quality.json`
- optional verlinkte Alert-/Shadow-Drill-Evidence aus `reports/`

## 7) Wann Datenqualitaet als verified gelten darf

Nur wenn alle Bedingungen erfuellt sind:

- Report basiert auf echten Runtime-Daten (`evidence_level=runtime`)
- `status=pass` fuer alle Live-kritischen Assets
- Exchange-Truth-Abgleich vorhanden
- Alert-Routing mit Zustellnachweis dokumentiert
- Zeitraum, Git-SHA, Umgebung und Owner-Review extern archiviert

## 8) Welche Datenfehler Live blockieren

- stale Ticker/Orderbook/Funding
- kritische Candle-Gaps oder fehlende Candles
- bid/ask inkonsistent, negative/ungueltige Preise
- starke Mark-vs-Index-Abweichung
- fehlender oder unklarer Exchange-Truth-Abgleich
- Provider/Redis/DB-Ausfall ohne belastbare Qualitaetsbewertung

## 9) Warum Paper/Shadow nicht gleich Live-Freigabe ist

Paper/Shadow beweist Logik und Guardrails, aber keine echte Produktionsstabilitaet unter realen Betriebsrisiken. Live bleibt `NO_GO`, bis Runtime-Evidence, Alert-Zustellung und Owner-Freigabe gemeinsam verifiziert sind.
