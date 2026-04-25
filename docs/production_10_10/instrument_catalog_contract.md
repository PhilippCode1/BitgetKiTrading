# Instrument Catalog Contract (Bitget)

## Zweck

Der Instrumentenkatalog ist die Single Source of Truth fuer das Asset-Universum
in `bitget-btc-ai`. Er trennt strikt zwischen sichtbar/chartbar/analysierbar,
paper/shadow und live-faehig.

## Pflichtfelder pro Asset

- `symbol`
- `base_coin`
- `quote_coin`
- `market_family`
- `product_type`
- `margin_coin`
- `status_on_exchange`
- `chart_available`
- `trading_available`
- `paper_allowed`
- `shadow_allowed`
- `live_allowed`
- `live_block_reasons`
- `tick_size`
- `lot_size`
- `min_qty`
- `min_notional`
- `price_precision`
- `quantity_precision`
- `funding_relevant`
- `open_interest_relevant`
- `last_metadata_refresh_ts`
- `metadata_source`
- `risk_tier`
- `liquidity_tier`
- `data_quality_status`
- `operator_note_de`

## Harte Live-Regeln

1. Fehlendes Asset im Katalog => kein Live.
2. `status_on_exchange in {delisted, suspended, unknown}` => kein Live.
3. Futures ohne `product_type` => kein Live.
4. Futures ohne `margin_coin` => kein Live.
5. Ohne `tick_size` oder `lot_size` => kein Live.
6. `live_allowed` ist niemals Default-`true`.
7. Neue Assets starten konservativ (`blocked`/`shadow_only`/Quarantaene).
8. Reports enthalten keine Secrets.
9. Blockgruende sind deutsch interpretierbar.
10. Live-Broker validiert zukuenftig gegen Katalog statt lose Symbollisten.

## Main-Console-Anbindung

Das Main-Console-Modul **Asset-Universum** zeigt:

- Anzahl erkannter Assets
- Anzahl aktiver Assets
- Anzahl blockierter Assets
- Anzahl in Quarantaene
- Anzahl shadowfaehiger Assets
- Anzahl livefaehiger Assets
- je Asset: Status, MarketFamily, ProductType, Risk-Tier, Liquidity-Tier,
  Datenqualitaet und Blockgruende
