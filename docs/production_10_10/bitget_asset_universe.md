# Bitget Asset Universe Governance

## 1) Zielbild Multi-Asset

`bitget-btc-ai` arbeitet nicht mit einer Single-Symbol-Denke. Die Plattform
erkennt und verwaltet Spot-, Margin- und Futures-Instrumente als kontrolliertes
Bitget-Asset-Universum mit klaren Live-Gates.

## 2) Warum nicht jedes Bitget-Asset automatisch livefaehig ist

Ein Asset darf nie live handeln, nur weil es auf Bitget existiert. Ohne
verifizierte Metadaten, Datenqualitaet, Liquiditaetsnachweis, Risk-Tier,
Strategie-Evidence und Owner-Freigabe bleibt es blockiert (fail-closed).

## 3) Marktfamilien

- `spot`
- `margin`
- `futures`

Alle Familien werden in einem gemeinsamen Instrumentkatalog modelliert; es gibt
keine zweite, parallele Symbol-Architektur.

Der Precision-/Order-Parameter-Vertrag ist bindend in:
`docs/production_10_10/instrument_precision_order_contract.md`.

## 4) Pflichtfelder pro Instrument

Pflichtstruktur fuer Governance (`BitgetAssetUniverseInstrument`):

- `symbol`, `base_coin`, `quote_coin`
- `market_family`, `product_type`, `margin_coin`, `margin_mode`
- `tick_size`, `lot_size`, `min_qty`, `min_notional`
- `price_precision`, `quantity_precision`
- `status`, `is_tradable`, `is_chart_visible`, `is_live_allowed`, `block_reasons`
- `discovered_at`, `last_verified_at`, `source`

Fehlende Pflichtdaten fuehren zu Live-Blockaden, z. B. fehlende Precision,
fehlendes `min_qty` oder fehlendes `min_notional`.

## 5) Asset-Statusmodell

Erlaubte Statuswerte:

- `unknown`
- `discovered`
- `active`
- `watchlist`
- `shadow_allowed`
- `live_candidate`
- `live_allowed`
- `quarantined`
- `delisted`
- `suspended`
- `blocked`

`unknown`, `quarantined`, `delisted`, `suspended` und `blocked` sind harte
Live-Blocker.

## 6) Asset-Tiers

- Tier 0: unknown/blocked (kein Live)
- Tier 1: sehr liquide Hauptassets
- Tier 2: liquide grosse Assets
- Tier 3: mittlere Assets mit erhoehtem Risiko
- Tier 4: illiquide/stark volatile Assets (Research/Shadow)
- Tier 5: delisted/suspended/banned (kein Live)

Tier 1 alleine reicht nicht: erst mit weiteren Gates und `live_candidate` kann
ein Asset livefaehig werden.

## 7) Live-Gates

Live ist nur erlaubt, wenn alle Gates gruen sind:

- Status ist nicht unknown/delisted/suspended/quarantined/blocked.
- Futures hat `product_type` und `margin_coin`.
- Precision (`price_precision`, `quantity_precision`) ist vorhanden.
- Min-Grenzen (`min_qty`, `min_notional`) sind vorhanden.
- Datenqualitaet ist ok.
- Liquiditaetspruefung ist ok.
- Risk-Tier ist zugewiesen.
- Strategie-Evidence liegt vor.
- Owner-Freigabe von Philipp liegt vor.
- `block_reasons` ist leer.

## 8) Quarantaene

Quarantaene ist ein expliziter Zustand und kein Hinweistext. Quarantaene
blockiert Live immer und wird nur nach dokumentierter Ursache + Re-Validierung
aufgehoben.

## 9) Delisting und Suspension

Delisting oder Suspension fuehren zu sofortiger Live-Sperre. Es gibt keinen
stillen Fallback, der alte Precision-/Leverage-Annahmen weiterverwendet.

## 10) Main-Console-Darstellung

Die Hauptkonsole zeigt pro Asset mindestens:

- Status
- Tier
- Live-Eligibility
- Blockgruende
- letzte Verifikation (`last_verified_at`)

Bei Blockaden ist die Anzeige klar als Go/No-Go Signal ausgefuehrt.

Zusaetzlich gibt es ein zentrales Modul **Asset-Universum** in der Main
Console mit diesen Kennzahlen:

- Anzahl erkannter Assets
- Anzahl aktiver Assets
- Anzahl blockierter Assets
- Anzahl in Quarantaene
- Anzahl shadowfaehiger Assets
- Anzahl livefaehiger Assets

Und pro Asset:

- Status auf der Boerse
- MarketFamily und ProductType
- Risk-Tier und Liquidity-Tier
- Datenqualitaetsstatus
- deutsche Blockgruende

## 11) Tests

Mindestens:

```bash
python scripts/refresh_bitget_asset_universe.py --dry-run
python scripts/refresh_bitget_asset_universe.py --input-json tests/fixtures/bitget_asset_universe_sample.json --output-json reports/bitget_asset_universe_sample.json --output-md reports/bitget_asset_universe_sample.md
python tools/check_bitget_asset_universe.py
python tools/check_bitget_asset_universe.py --strict
python tools/check_bitget_asset_universe.py --json
pytest tests/shared/test_bitget_asset_universe.py -q
pytest tests/tools/test_check_bitget_asset_universe.py -q
pytest tests/security/test_bitget_asset_universe_contracts.py -q
```

## 12) No-Go-Regeln

- Keine BTCUSDT-Default-Freigabe.
- Keine automatische Live-Freigabe fuer alle entdeckten Assets.
- Kein Live ohne vollstaendige Asset-Gates.
- Kein Umgehen von Quarantaene, Delisting oder Suspension.
- Keine Abschwaechung der globalen Live-Gates aus `AGENTS.md` und
  `docs/production_10_10/no_go_rules.md`.
- Ohne dokumentierte Asset-Freigabe bleibt jede Live-Entscheidung `NO_GO`.
