# Structure Engine (Prompt 11)

Der Service `structure-engine` konsumiert `events:candle_close`, berechnet pro
**Symbol + Timeframe** Marktstruktur und persistiert in Postgres. Bei relevanter
Änderung wird `events:structure_updated` publiziert (`EventEnvelope`,
`event_type=structure_updated`).

## HTTP

- `GET /health`
- `GET /structure/latest?symbol=<example_symbol>&timeframe=1m`

## Datenbanktabellen (`050_structure.sql`)

- `app.swings` – bestätigte Pivot-Swings (High/Low)
- `app.structure_state` – letzter Zustand inkl. Trend, Kompression, `breakout_box_json`
- `app.structure_events` – Ereignisse (`BOS`, `CHOCH`, `BREAKOUT`,
  `FALSE_BREAKOUT`, `COMPRESSION_ON`, `COMPRESSION_OFF`) mit `details_json`

Richtungen für BOS/CHOCH liegen in `details_json` unter `direction` (`UP`/`DOWN`).

## Pivot (Swings)

Parameter **je Timeframe** über ENV, z. B. `PIVOT_LEFT_N_1M` / `PIVOT_RIGHT_N_1M`.

- **Swing High** an Kerze `i`, wenn `high[i]` das **Maximum** im Fenster
  `[i - left_n, i + right_n]` ist.
- **Swing Low** analog mit **Minimum** der Lows.
- **Bestätigung**: erst wenn `right_n` Kerzen **nach** `i` geschlossen sind
  (verzögerte Bestätigung, kein Repaint der letzten `right_n` Bars).

`confirmed_ts_ms` ist der Zeitstempel der **letzten** Kerze im Buffer (die
bestätigende Close-Bar).

## Trend

- **UP**: letzte zwei bestätigte Swing-Highs und -Lows erfüllen **HH + HL**.
- **DOWN**: **LL + LH**.
- Sonst **RANGE**.

Trend wird **nur** aus gespeicherten/bestätigten Swings abgeleitet.

## BOS / CHOCH (Close-Regeln)

Auf Basis von `trend_dir` und den **letzten** bestätigten Swing-Levels:

| Trend | Bedingung (Close)          | Event-Typ | `details.direction` |
| ----- | -------------------------- | --------- | ------------------- |
| UP    | Close > letztes Swing-High | `BOS`     | `UP`                |
| UP    | Close < letztes Swing-Low  | `CHOCH`   | `DOWN`              |
| DOWN  | Close < letztes Swing-Low  | `BOS`     | `DOWN`              |
| DOWN  | Close > letztes Swing-High | `CHOCH`   | `UP`                |

Im Worker wird pro Bar nur ein **Kanten-Event** erzeugt (Übergang von „nicht
erfüllt“ zu „erfüllt“), damit es nicht bei jeder weiteren Kerze spammt.

## Kompression (Squeeze)

- **ATR%** = `atr_14 / close` (oder Fallback: lokale TR-SMA(14)/close, wenn die
  Feature-Zeile fehlt – mit Log).
- **Range20** = `(max(high der letzten 20) − min(low der letzten 20)) / close`.

**EIN** (mit „Range sinkt“): `ATR% < COMPRESSION_ATRP_THRESH` und
`Range20 < COMPRESSION_RANGE_THRESH` und `Range20` ist gegenüber der **vorherigen**
Bar gesunken (oder es gibt noch keinen Referenzwert).

**AUS** (Hysterese): `ATR% > COMPRESSION_ATRP_THRESH_OFF` **oder**
`Range20 > COMPRESSION_RANGE_THRESH_OFF`.

## Breakout-Box

Wenn `compression_flag = true`:

- `box_high` / `box_low` über die letzten `N_box` Kerzen (`BOX_WINDOW_*` per TF).
- **Pre-Breakout-Kandidat**: Close innerhalb `BOX_PREBREAK_DIST_BPS` (Basis-Punkte)
  von `box_high` oder `box_low`.

## False Breakout

- **Breakout oben**: `Close > box_high + buffer` mit `buffer = box_high * (BOX_BREAKOUT_BUFFER_BPS / 10_000)`  
  → Event `BREAKOUT`, danach Beobachtungsfenster `FALSE_BREAKOUT_WINDOW_BARS`.
- **False Breakout oben**: innerhalb des Fensters wieder `Close <= box_high`  
  → `FALSE_BREAKOUT` mit `details.side` = `UP`.

Unten spiegelbildlich mit `box_low`.

## Redis-Stream Payload (`structure_updated`)

`payload` enthält u. a.:

- `ts_ms`, `trend_dir`
- `swings` (letzte IDs/Typen/Preise)
- `compression_flag`
- `breakout_box` (`high`, `low`, `start_ts_ms`, `end_ts_ms`) oder `null`

## ENV

Siehe `.env.example` (Abschnitt Structure Engine).
