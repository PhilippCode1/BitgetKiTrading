# Liquidity Runtime Evidence Guide

Diese Anleitung beschreibt, wie Philipp echte Runtime-Evidence fuer `liquidity_spread_slippage_per_asset` erzeugt, ohne Live-Trades auszufuehren.

## 1) Welche Services laufen muessen

- `market-stream` (Orderbook/Ticker-Livefeeds)
- `feature-engine` (Mikrostruktur-/Staleness-Kontext)
- `signal-engine` (Pre-Trade-Qualitaetskontext)
- `live-broker` (nur Preflight/Failsafe, keine Live-Orders)
- Redis/Postgres fuer frische, reproduzierbare Snapshot-Kette

## 2) Wie Orderbookdaten gesammelt werden

- pro Asset fortlaufend Top-of-Book und Top-5/Top-10-Tiefe erfassen
- `ts_ms` aus Feed persistieren
- keine synthetischen Backfills als Runtime-Evidence markieren

## 3) Welche Assets geprueft werden

- mindestens: BTCUSDT, ETHUSDT
- je Asset-Familie mindestens ein Spot-, Margin- und Futures-Asset
- alle Assets, die fuer private Live vorgesehen sind

## 4) Wie lange das Fenster laufen soll

- mindestens 60 Minuten stabile Datenerfassung
- bei auffaelligen Spreads/Desyncs: neues, sauberes Fenster starten

## 5) Welche Grenzwerte gelten

- stale orderbook -> block
- spread ueber Asset-Limit -> block
- slippage ueber Asset-Limit -> block
- unzureichende Tiefe/Depth-Ratio -> block
- Market-Order ohne Slippage-Gate -> block

## 6) Welche Kommandos auszufuehren sind

```bash
python scripts/liquidity_spread_slippage_evidence_report.py --output-md reports/liquidity_spread_slippage_evidence.md --output-json reports/liquidity_spread_slippage_evidence.json
python tools/check_live_broker_preflight.py --strict
```

## 7) Welche Reports entstehen

- `reports/liquidity_spread_slippage_evidence.md`
- `reports/liquidity_spread_slippage_evidence.json`
- `reports/live_broker_preflight_matrix.md`

## 8) Wann `liquidity_spread_slippage_per_asset` verified werden darf

Nur wenn:

- Runtime-Orderbookdaten (kein synthetic) vorliegen
- Asset-Grenzwerte und Blocker reproduzierbar eingehalten sind
- Report Zeitraum, Assets, Git-SHA, Umgebung, Owner-Review dokumentiert
- keine Market-Order ohne Slippage-Gate moeglich ist

## 9) Warum schlechte Liquiditaet Live blockiert

Schlechte Liquiditaet fuehrt zu unkontrollierbarer Ausfuehrung (Spread-/Slippage-Schock, Fill-Risiko, Exit-Risiko). Deshalb gilt fail-closed: unklar/duenn/stale = kein Live-Submit.
