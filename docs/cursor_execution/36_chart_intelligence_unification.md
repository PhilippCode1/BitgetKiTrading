# 36 — Chart-Intelligence: gemeinsame Overlay-Schicht

## Ziel

Eine **einheitliche technische Basis** für Kerzen-Overlays (Strategie-Levels, optional Live-KI-Geometrie, Terminal-Struktur/News), damit **Terminal**, **Konsole/Ops** und **Signaldetail** nicht jeweils eigene Regeln erfinden. **Keine heimliche Aktivierung:** erlaubte Overlay-Klassen pro Fläche stehen in `CHART_SURFACE_ALLOWLIST`; Nutzer-Toggles (z. B. Zeichnungen/News im Terminal) wirken nur innerhalb dieser Allowlist.

Referenzen: `docs/chatgpt_handoff/05_DATENFLUSS_BITGET_CHARTS_UND_PIPELINE.md`, `06_KI_ORCHESTRATOR_UND_STRATEGIE_SICHTBARKEIT.md`, `07_FRONTEND_UX_SPRACHE_UND_DESIGN_AUDIT.md`.

## Overlay-Matrix (Allowlist)

| Overlay-Klasse                                             | `console_market` | `signal_detail` | `terminal`                  |
| ---------------------------------------------------------- | ---------------- | --------------- | --------------------------- |
| **Strategie-Preislevels** (Gateway-Signal + Referenzpreis) | ja               | ja              | ja                          |
| **LLM-Chart-Geometrie** (`chart_annotations` → Sanitizer)  | nein             | ja              | nein                        |
| **Struktur-Zeichnungen** (`app.drawings`)                  | nein             | nein            | ja (× Nutzer-Toggle)        |
| **News-Marker**                                            | nein             | nein            | ja (× Nutzer-Toggle)        |
| **Lineage-Panel** (Panel neben Chart, kein Canvas)         | nein             | nein            | ja (`LiveDataLineagePanel`) |

**Hinweise**

- **Risiko-Hinweise** aus `GET /v1/signals/{id}/explain` (`risk_warnings_json`) werden im Signaldetail als **Text-Panel** geführt, nicht als Kerzen-Overlay — siehe Task 35. KI-Risiko-Zeilen in **Chart-Notizen** können in `chart_notes_de` innerhalb der LLM-Annotation landen und werden mit der LLM-Geometrie gesäubert (`sanitizeLlmChartAnnotations`).
- **Deterministische** Strategie-Linien nutzen weiterhin nur numerische Backend-Felder (`strategy-overlay-model`).

## Komponenten- und Modulpfade

| Rolle                                      | Pfad                                                                                                                              |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| Allowlist, Resolver, Strategie-Bundle      | `apps/dashboard/src/lib/chart/chart-intelligence.ts`                                                                              |
| LLM-Sanitize (bestehend)                   | `apps/dashboard/src/lib/chart/llm-chart-annotations.ts`                                                                           |
| Kerzen-Widget inkl. Strategie- + LLM-Layer | `apps/dashboard/src/components/chart/ProductCandleChart.tsx`                                                                      |
| Konsole/Ops/Health/… Marktchart            | `apps/dashboard/src/components/console/ConsoleLiveMarketChartSection.tsx` (`chartSurfaceId`, Default `console_market`)            |
| Signaldetail-Chart                         | `apps/dashboard/src/components/signals/SignalDetailMarketChartBlock.tsx` → `chartSurfaceId="signal_detail"`                       |
| Live-Terminal-Chart                        | `apps/dashboard/src/components/live/ChartPanel.tsx` (verwendet `CHART_SURFACE_ALLOWLIST.terminal`, `llmChartIntegration={false}`) |
| Lineage neben Terminal                     | `apps/dashboard/src/components/live/LiveTerminalClient.tsx` → `LiveDataLineagePanel`                                              |

## Guardrails

1. **`resolveEffectiveLlmChartIntegration`:** Setzt LLM-Canvas auf **false**, wenn die Surface-Allowlist `llmChartGeometry: false` hat — auch wenn ein Eltern-Prop `llmChartIntegration` irrtümlich `true` wäre (Konsole).
2. **`buildStrategyMarkerOverlayBundle`:** Einziger empfohlener Einstieg für `buildStrategyOverlayModel` + `buildStrategyOverlayChartLines` aus Live-State-Kontexten.
3. **Terminal:** Zeichnungen/News nur wenn Allowlist **und** bestehende UI-Toggles (`showDrawings`, `showNewsMarkers`) true sind.

## Nachweise

### Typprüfung (automatisch)

```text
cd apps/dashboard
pnpm check-types
pnpm test -- src/lib/chart/__tests__/chart-intelligence.test.ts --runInBand
```

### Zwei Chart-Flächen (manuell / Repo-Beleg)

1. **Konsole Marktchart** (z. B. `console/signals`, `console/ops`): Strategie-Legende und ggf. Levels erscheinen bei passendem `latest_signal`; **kein** violetter LLM-Layer ohne Signaldetail-Context.
2. **Signaldetail** (`console/signals/[id]`): `SignalDetailMarketChartBlock` mit `chartSurfaceId="signal_detail"` — LLM-Overlays nur nach Anfrage im Strategy-Signal-Explain-Panel und mit sichtbarem Toggle (bestehende UX).

### UI-Komponenten

- `ConsoleLiveMarketChartSection` und `ChartPanel` importieren dieselbe Schicht (`chart-intelligence`); `ProductCandleChart` bleibt die gemeinsame Render-Basis.

## Offene Punkte

- **[FUTURE]** Weitere Surfaces (z. B. dediziertes „nur Kerzen“-Preset) als weiterer `ChartSurfaceId` mit Allowlist-Eintrag.
- **[FUTURE]** Optional ein Hook `useChartIntelligence(surfaceId)` — aktuell bewusst schlank gehalten (pure Functions).
