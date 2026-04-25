# Signal- und KI-Entscheidungscenter

Status: implemented

## Ziel

Das Signal-Modul der Main Console zeigt Entscheidungsgrundlagen in deutscher Sprache:
Signalrichtung, Staerke, Risk-Gates, Blockgruende, Asset-Kontext und KI-Erklaerung.
Die KI ist strikt advisory und hat keine Ausfuehrungsbefugnis.

## Umgesetzte Sicht im Dashboard

- Signale-Liste erweitert um:
  - deutsche Trade-Action-Labels (`allow_trade`, `do_not_trade`, `review_required`, `blocked`)
  - Risk-Status
  - deutsche Blockgruende
  - Datenalter
- Signal-Detail erweitert um:
  - Asset-Tier
  - Datenqualitaet
  - Liquiditaetsstatus
  - Live-Freigabestatus
  - Risk-Governor-/Blockgruende
- Live-KI-Bereich mit klarem Hinweis:
  - `KI-Hinweis: keine Ausfuehrungsbefugnis.`

## LLM-Grenzen (Fail-Closed)

- Antworten mit `execution_authority != none` werden im Frontend verworfen.
- Fehlende LLM-Erklaerung aendert keinen Signalstatus und oeffnet keinen Trade.
- Fehlertexte werden redigiert (Token/Secret-Marker maskiert), um Secret-Leaks zu vermeiden.
- Fake-Provider in Produktion bleibt backendseitig verboten (`LLM_USE_FAKE_PROVIDER` Guard).

## Prompt-Injection-Abgrenzung

- News- und Freitextkontext bleibt advisory; Ausfuehrung und Freigabe laufen weiterhin
  ueber deterministische Serverpfade (Risk-Governor, Live-Gates, Broker-Freigaben).
- LLM-Ausfall fuehrt zu Erklaerungsdegradation, nicht zu Trading-Freigaben.

## Relevante Dateien

- `apps/dashboard/src/components/tables/SignalsTable.tsx`
- `apps/dashboard/src/components/signals/SignalDetailRiskStrategySection.tsx`
- `apps/dashboard/src/components/signals/SignalDetailLiveAiSection.tsx`
- `apps/dashboard/src/components/panels/StrategySignalExplainPanel.tsx`
- `apps/dashboard/src/lib/signal-decision-center.ts`
- `apps/dashboard/src/lib/strategy-signal-explain-errors.ts`
- `apps/dashboard/src/lib/operator-explain-errors.ts`
