import type { LiveSignal } from "@/lib/types";

/**
 * Referenzpreis fuer Strategie-Linien (Gateway-Daten, feste Prioritaet).
 * Mark > Ticker-Last > Schlusskurs der letzten Kerze.
 */
export type StrategyReferenceSource =
  | "mark_price"
  | "ticker_last"
  | "last_candle_close";

export const STRATEGY_OVERLAY_LAYERS = [
  "reference",
  "stop_loss",
  "take_profit_mfe",
  "risk_mae",
  "stop_budget_max",
  "stop_min_executable",
] as const;

export type StrategyOverlayLayerId = (typeof STRATEGY_OVERLAY_LAYERS)[number];

export type StrategyOverlayLine = Readonly<{
  id: StrategyOverlayLayerId;
  price: number;
}>;

export type StrategyOverlayModel = Readonly<{
  reference: Readonly<{
    price: number;
    source: StrategyReferenceSource;
  }> | null;
  lines: readonly StrategyOverlayLine[];
  direction: "long" | "short" | null;
  /** Nur Text aus Backend-Feldern — keine erfundenen Preise */
  regimeText: string | null;
  invalidationText: string | null;
}>;

function finitePositive(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n) && n > 0;
}

/** stop_distance_pct ist Anteil am Preis (Backend/Exit-Engine: |entry-stop|/entry). */
function finiteRatio(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n) && n > 0 && n < 1;
}

export function normalizeSignalDirection(
  direction: string | null | undefined,
): "long" | "short" | null {
  if (direction == null) return null;
  const d = direction.trim().toLowerCase();
  if (d === "long" || d === "buy" || d === "bull" || d === "b") return "long";
  if (d === "short" || d === "sell" || d === "bear" || d === "s")
    return "short";
  return null;
}

export function resolveStrategyReferencePrice(input: {
  markPrice: number | null | undefined;
  tickerLast: number | null | undefined;
  lastCandleClose: number | null | undefined;
}): Readonly<{ price: number; source: StrategyReferenceSource }> | null {
  if (finitePositive(input.markPrice)) {
    return { price: input.markPrice, source: "mark_price" };
  }
  if (finitePositive(input.tickerLast)) {
    return { price: input.tickerLast, source: "ticker_last" };
  }
  if (finitePositive(input.lastCandleClose)) {
    return { price: input.lastCandleClose, source: "last_candle_close" };
  }
  return null;
}

function joinBackendStrings(
  parts: Array<string | null | undefined>,
): string | null {
  const s = parts
    .filter((x): x is string => typeof x === "string" && x.trim().length > 0)
    .map((x) => x.trim());
  if (s.length === 0) return null;
  return [...new Set(s)].join(" · ");
}

function buildInvalidationLine(signal: LiveSignal): string | null {
  const parts: string[] = [];
  if (typeof signal.trade_action === "string" && signal.trade_action.trim()) {
    parts.push(`trade_action=${signal.trade_action.trim()}`);
  }
  if (
    typeof signal.decision_state === "string" &&
    signal.decision_state.trim()
  ) {
    parts.push(`decision_state=${signal.decision_state.trim()}`);
  }
  if (
    typeof signal.regime_transition_state === "string" &&
    signal.regime_transition_state.trim()
  ) {
    parts.push(`regime_transition=${signal.regime_transition_state.trim()}`);
  }
  return parts.length ? parts.join(" · ") : null;
}

function buildRegimeText(signal: LiveSignal): string | null {
  return joinBackendStrings([
    signal.market_regime,
    signal.regime_state,
    signal.regime_substate,
    signal.regime_bias,
  ]);
}

/**
 * Aus Live-Signal + Referenzpreis: horizontale Levels strikt aus numerischen Backend-Feldern.
 * Keine Schaetzung, wenn Richtung oder Pflichtfelder fehlen.
 */
export function buildStrategyOverlayModel(input: {
  signal: LiveSignal | null;
  reference: Readonly<{
    price: number;
    source: StrategyReferenceSource;
  }> | null;
}): StrategyOverlayModel {
  const nullResult: StrategyOverlayModel = {
    reference: input.reference,
    lines: [],
    direction: null,
    regimeText: null,
    invalidationText: null,
  };

  if (!input.signal || !input.reference) {
    if (input.signal) {
      return {
        ...nullResult,
        regimeText: buildRegimeText(input.signal),
        invalidationText: buildInvalidationLine(input.signal),
      };
    }
    return nullResult;
  }

  const signal = input.signal;
  const ref = input.reference.price;
  const dir = normalizeSignalDirection(signal.direction);
  const lines: StrategyOverlayLine[] = [];

  lines.push({ id: "reference", price: ref });

  if (dir && finiteRatio(signal.stop_distance_pct)) {
    const p = signal.stop_distance_pct;
    const stop = dir === "long" ? ref * (1 - p) : ref * (1 + p);
    if (Number.isFinite(stop) && stop > 0) {
      lines.push({ id: "stop_loss", price: stop });
    }
  }

  if (
    dir &&
    typeof signal.expected_mfe_bps === "number" &&
    Number.isFinite(signal.expected_mfe_bps)
  ) {
    const bps = Math.abs(signal.expected_mfe_bps);
    if (bps > 0) {
      const tp =
        dir === "long" ? ref * (1 + bps / 10_000) : ref * (1 - bps / 10_000);
      if (Number.isFinite(tp) && tp > 0) {
        lines.push({ id: "take_profit_mfe", price: tp });
      }
    }
  }

  if (
    dir &&
    typeof signal.expected_mae_bps === "number" &&
    Number.isFinite(signal.expected_mae_bps)
  ) {
    const bps = Math.abs(signal.expected_mae_bps);
    if (bps > 0) {
      const risk =
        dir === "long" ? ref * (1 - bps / 10_000) : ref * (1 + bps / 10_000);
      if (Number.isFinite(risk) && risk > 0) {
        lines.push({ id: "risk_mae", price: risk });
      }
    }
  }

  if (dir && finiteRatio(signal.stop_budget_max_pct_allowed)) {
    const p = signal.stop_budget_max_pct_allowed;
    const px = dir === "long" ? ref * (1 - p) : ref * (1 + p);
    if (Number.isFinite(px) && px > 0) {
      lines.push({ id: "stop_budget_max", price: px });
    }
  }

  if (dir && finiteRatio(signal.stop_min_executable_pct)) {
    const p = signal.stop_min_executable_pct;
    const px = dir === "long" ? ref * (1 - p) : ref * (1 + p);
    if (Number.isFinite(px) && px > 0) {
      lines.push({ id: "stop_min_executable", price: px });
    }
  }

  return {
    reference: input.reference,
    lines,
    direction: dir,
    regimeText: buildRegimeText(signal),
    invalidationText: buildInvalidationLine(signal),
  };
}

export function defaultStrategyLayerVisibility(): Record<
  StrategyOverlayLayerId,
  boolean
> {
  return {
    reference: true,
    stop_loss: true,
    take_profit_mfe: true,
    risk_mae: true,
    stop_budget_max: true,
    stop_min_executable: true,
  };
}
