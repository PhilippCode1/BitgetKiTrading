# Asset-Quarantaene und Live-Allowlist

## Zielbild

Das Asset-Universum darf nicht automatisch zu Live-Trading fuehren. Jedes Asset
geht durch einen expliziten Freigabeprozess fuer Philipp als einzigen
Owner/Admin/Operator.

## Asset-Zustaende

- `unknown`
- `discovered`
- `quarantine`
- `research_only`
- `paper_allowed`
- `shadow_allowed`
- `live_candidate`
- `live_allowed`
- `blocked`
- `delisted`
- `suspended`
- `manual_review_required`

## Transition-Regeln

- `discovered -> quarantine` automatisch moeglich.
- `quarantine -> paper_allowed` nur mit vollstaendigen Instrumentendaten.
- `paper_allowed -> shadow_allowed` nur mit stabiler Datenqualitaet/Katalog.
- `shadow_allowed -> live_candidate` nur mit Risk-Tier, Liquidity-Tier,
  Strategy-Evidence und Bitget-Readiness.
- `live_candidate -> live_allowed` nur mit expliziter Philipp-Freigabe inkl.
  Zeitstempel, Actor und deutschem Grund.

Direkte Spruenge wie `discovered -> live_allowed` sind verboten.

## Harte Regeln

1. `discovered`, `quarantine`, `research_only` sind nie live.
2. `paper_allowed`, `shadow_allowed`, `live_candidate` senden keine echten Orders.
3. `live_allowed` braucht Actor `Philipp`, Reason und Evidence.
4. `blocked`, `delisted`, `suspended` blockieren alles ausser Anzeige/Historie.
5. Ohne Datenqualitaet/Liquiditaet/Strategy-Evidence/Bitget-Status kein Live.
6. Deutsche Block-/Freigabegruende sind Pflicht.

## Audit-Felder

- `asset_id`
- `symbol`
- `market_family`
- `product_type`
- `from_state`
- `to_state`
- `actor`
- `reason_de`
- `evidence_refs`
- `created_at`
- `expires_at`
- `risk_tier`
- `liquidity_tier`
- `data_quality_status`

## Main Console Modul: Asset-Freigaben

Die Main Console zeigt im Modul **Asset-Freigaben**:

- Live erlaubt
- Nur Shadow
- Nur Paper
- In Quarantaene
- Blockiert
- Manuelle Pruefung noetig
- Warum blockiert?
- Welche Evidence fehlt?
