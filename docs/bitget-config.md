# Bitget Config

## Ziel

Das Modul `shared_py.bitget.config.BitgetSettings` kapselt die Bitget-Konfiguration
fuer Live- und Demo-Modus an einer Stelle. Es laedt ENV-Werte, validiert Domains,
normalisiert `BITGET_SYMBOL` und fuehrt einen **kanonischen Instrumentvertrag**
mit `BITGET_MARKET_FAMILY`, `BITGET_PRODUCT_TYPE`, `BITGET_MARGIN_ACCOUNT_MODE`
und `BITGET_MARGIN_COIN` ein. Im Demo-Modus setzt es weiterhin den REST-Header
`paptrading: 1`.

`shared_py.bitget.instruments` und `shared_py.bitget.discovery` liefern dazu
family-aware Endpoint-Profile und Discovery-Hilfen fuer `spot`, `margin` und
`futures`. Der Service `services/live-broker/` verwendet genau dieses gemeinsame
Settings-Modul fuer REST-Probes, Shadow-Entscheidungen und die spaetere
Private-Execution-Freigabe. Es gibt dafuer keine zweite, service-spezifische
Bitget-Konfigurationsquelle.

**Architektur-Referenz:** `docs/adr/ADR-0001-bitget-market-universe-platform.md`

## Marktfamilien

- `BITGET_MARKET_FAMILY=futures`: klassische Bitget-Perps/Contracts ueber `/api/v2/mix/*`
- `BITGET_MARKET_FAMILY=spot`: Spot-Markt ueber `/api/v2/spot/*`
- `BITGET_MARKET_FAMILY=margin`: Margin-Execution mit Spot-Market-Data plus Margin-Private-REST (`isolated` oder `crossed`)

Fuer `margin` bleibt die Family **erst dann operativ freigegeben**, wenn sie durch
reale Account-/Metadata-Responses sichtbar ist. Der Discovery-Client markiert nur
Familien/Symbole, die ueber aktuelle Endpunkte wirklich beobachtbar sind.

Weitere Bitget-Kategorien werden nur dann aufgenommen, wenn sie:

- ueber aktuelle Metadata-/Market-Endpunkte real auffindbar sind
- in das kanonische Instrumentmodell passen
- mit Capability-Flags als sichtbar, analysetauglich und ggf. handelbar markiert werden

Es gibt **keine** hart angenommene Liste exotischer Produkte.

## Marktinventar als Grenze

Im Zielbild ist das Marktinventar eine eigene fachliche Grenze:

- Discovery bestimmt, was das Konto und die API real exponieren.
- Eventbus, Registry, Broker und Dashboard konsumieren Instrumentidentitaeten aus diesem Inventar.
- Ein einzelnes `symbol` ohne Family-/Capability-Kontext reicht im Produktionsziel nicht mehr aus.

## Zentraler Instrumentenkatalog

Der zentrale Instrumentenkatalog wird als aktueller Snapshot in der App-Datenbank und im Redis-Cache gehalten:

- Snapshot-Historie: `app.instrument_catalog_snapshots`
- aktueller Katalog: `app.instrument_catalog_entries`
- Cache: Redis-Key fuer den aktuellen Snapshot

Der Katalog normiert mindestens:

- kanonische Instrument-ID
- Symbolaliasliste
- Marktfamilie
- Margin-/Quote-/Settlement-Coin
- Tick-/Step-Parameter
- Minimalmengen / minimale Notional-Grenzen
- Maximalmengen fuer Limit-/Market-Orders, soweit exponiert
- Hebelgrenzen, falls durch die aktuelle Bitget-Metadatenlage real exponiert
- Trading- und Subscribe-Status
- Session- und Lifecycle-Metadaten
- Funding-Zyklen, Delivery-/Maintenance-Zeitfenster und Family-spezifische Rohfelder

Darauf sitzt der Shared-Layer `shared_py.bitget.metadata.BitgetInstrumentMetadataService`.
Er liefert die **aufgeloeste, versionierte Metadatensicht** fuer:

- Order-Preflight
- Stop/TP-Validierung
- Hebel-Grenzen
- Health-/Operator-Sicht

### Refresh / Cache / Health

- `market-stream` ist im aktuellen Monorepo der primaere Refresh-Pfad fuer den Katalog.
- Weitere Dienste konsumieren denselben Snapshot ueber DB/Cache, statt Produkt- oder Symbolkonstanten hart zu verdrahten.
- Der Metadatenservice bewertet pro Instrument zusaetzlich **Health-Zustaende** wie `ok`, `degraded`, `unavailable`.
- Wichtige ENV-Grenzen:
  - `INSTRUMENT_CATALOG_REFRESH_INTERVAL_SEC`
  - `INSTRUMENT_CATALOG_CACHE_TTL_SEC`
  - `INSTRUMENT_CATALOG_MAX_STALE_SEC`

### Fallback-Regel

Ein unbekanntes oder nicht sauber katalogisiertes Instrument ist **kein** stiller Default-Fall.

- Unknown instrument → `no-trade`
- Unknown instrument → `no-subscribe`
- Delisting / Statusverlust → Katalogstatus wird heruntergestuft, statt mit alten Precision-/Trading-Annahmen weiterzulaufen

Weitere fail-closed Regeln:

- Maintenance / `restrictedAPI` / `off` → kein API-Trade
- Delivery- oder close-only Fenster → keine neuen Eroeffnungen
- unvollstaendige Pflichtmetadaten → degradierter Health-Zustand und Preflight-Block

## Asset Universe Governance (Multi-Asset)

Das Repo nutzt eine explizite Governance-Schicht fuer Asset-Livefaehigkeit:
`shared_py.bitget.instruments.BitgetAssetUniverseInstrument`.

Erlaubte Statuswerte:

- `unknown`, `discovered`, `active`, `watchlist`
- `shadow_allowed`, `live_candidate`, `live_allowed`
- `quarantined`, `delisted`, `suspended`, `blocked`

Tier-Grundlage:

- Tier 0 = blockiert
- Tier 1 = hochliquide Kernassets
- Tier 2/3 = abgestufte Risiko-/Liquiditaetsprofile
- Tier 4 = shadow/research-only
- Tier 5 = delisted/suspended/banned

Harte Live-Blocker (fail-closed):

- unknown / delisted / suspended / quarantined / blocked
- futures ohne `product_type` oder ohne `margin_coin`
- fehlende Precision (`price_precision` oder `quantity_precision`)
- fehlende Mindestwerte (`min_qty`, `min_notional`)
- fehlende Datenqualitaets-, Liquiditaets-, Risk-Tier-, Strategie- oder Owner-Gates
- nicht-leere `block_reasons`

Die Evaluierung laeuft ueber
`evaluate_asset_universe_live_eligibility(...)` und setzt `is_live_allowed`
nur dann auf true, wenn keine Blockgruende verbleiben.

## Private REST Auth

Fuer private REST-Aufrufe orientiert sich der Repo-Client an der offiziellen Bitget-
Dokumentation:

- Header: `ACCESS-KEY`, `ACCESS-SIGN`, `ACCESS-TIMESTAMP`, `ACCESS-PASSPHRASE`,
  `Content-Type: application/json`, `locale`
- Signaturformel: `timestamp + METHOD + requestPath + [?queryString] + body`
- Signaturverfahren: `HMAC SHA256`, danach `Base64`
- Serverzeit-Referenz: `GET /api/v2/public/time`
- Request-Fenster: Bitget dokumentiert fuer Auth-Requests ein 30-Sekunden-Zeitfenster;
  der `live-broker` synchronisiert deshalb regelmaessig die Serverzeit und verwendet
  einen konfigurierbaren Skew-Budget-Check

Der `live-broker` verwendet fuer private REST-Aufrufe zusaetzlich:

- `BITGET_MARGIN_COIN` fuer Futures-Margin-Coin bzw. Spot-/Margin-Coin-Kontext
- `BITGET_REST_LOCALE` fuer den offiziellen `locale`-Header
- `ORDER_IDEMPOTENCY_PREFIX` fuer deterministische `clientOid`-Ableitung aus internen
  Order-IDs
- `INTERNAL_API_KEY` fuer direkte produktionskritische Service-Zugriffe

## Demo vs Live

- Live REST Domain: `https://api.bitget.com`
- Live WS Domains: `wss://ws.bitget.com/v2/ws/public` und `wss://ws.bitget.com/v2/ws/private`
- Demo REST bleibt auf der offiziellen REST-Domain, benoetigt aber Demo-Keys und den Header `paptrading: 1`
- Demo WS Domains nutzen offiziell die `wspap.bitget.com`-Hosts

Wenn `BITGET_DEMO_ENABLED=true` ist, verwendet `BitgetSettings` automatisch die
Demo-REST- und Demo-WS-Werte als effektive Endpunkte.

## ENV-Dateien

- `.env.example` bleibt die committete Vorlage ohne Secrets
- `.env.local` ist lokal-only und darf niemals committed werden
- Leere Key-Felder bleiben erlaubt, damit public-data-first Workflows ohne API-Keys starten koennen

## Wichtige Properties

- `effective_rest_base_url`: liefert je nach Toggle Live- oder Demo-REST
- `effective_ws_public_url`: liefert je nach Toggle Live- oder Demo-Public-WS
- `effective_ws_private_url`: liefert je nach Toggle Live- oder Demo-Private-WS
- `rest_product_type_param`: gibt `BITGET_PRODUCT_TYPE` im REST-Format lowercase zurueck; fuer `spot`/`margin` bewusst `None`
- `endpoint_profile`: family-aware REST-/WS-Profil
- `instrument_identity(...)`: kanonische Instrumentbeschreibung fuer Events, Registry und Audit
- `discovery_symbols`: deduplizierte Kandidatenliste fuer account-/metadata-getriebene Discovery
- `build_rest_headers(...)`: haengt den Demo-Header auch fuer `live-broker`-REST-Probes
  und spaetere Order-Releases konsistent an
- `effective_api_key` / `effective_api_secret` / `effective_api_passphrase`: waehlen je
  nach Demo-Toggle automatisch den richtigen Credential-Satz
- `effective_margin_coin`: liefert fuer Futures `BITGET_MARGIN_COIN` oder den konsistenten
  Futures-Default (`USDT`/`USDC`); fuer Spot/Margin bleibt der Wert leer oder explizit gesetzt

Beispiele fuer `rest_product_type_param`:

- `USDT-FUTURES` -> `usdt-futures`
- `USDC-FUTURES` -> `usdc-futures`
- `COIN-FUTURES` -> `coin-futures`

## Demo Header

Bitget Demo-REST verlangt offiziell den Header `paptrading: 1`. Das Modul liefert
ihn ueber `demo_headers()` oder `build_rest_headers(...)` automatisch, sobald
`BITGET_DEMO_ENABLED=true` ist.

## Beispiele

```python
from shared_py.bitget.config import BitgetSettings

settings = BitgetSettings()

print(settings.effective_rest_base_url)
print(settings.effective_ws_public_url)
print(settings.rest_product_type_param)
print(settings.demo_headers())
```

```python
from shared_py.bitget import BitgetSettings, build_rest_headers

settings = BitgetSettings()
headers = build_rest_headers(settings, {"Accept": "application/json"})
print(headers)
```

## Validierung

- REST-URLs muessen mit `https://` beginnen
- WS-URLs muessen mit `wss://` beginnen
- `BITGET_SYMBOL` folgt Bitget v2, also z. B. `<example_symbol>` statt Legacy-Suffixen wie `_UMCBL`
- `BITGET_MARKET_FAMILY` muss `spot`, `margin` oder `futures` sein
- `BITGET_PRODUCT_TYPE` bleibt fuer Futures auf `USDT-FUTURES`, `USDC-FUTURES` und `COIN-FUTURES` begrenzt
- Im Demo-Modus muessen die effektiven WS-URLs auf der offiziellen `wspap.bitget.com`-Domain liegen
