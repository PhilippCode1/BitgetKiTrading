import type {
  AlertOutboxItem,
  LiveBrokerDecisionItem,
  LiveBrokerFillItem,
  PaperTradeRow,
} from "@/lib/types";

export type DecisionBuckets = {
  planQueue: LiveBrokerDecisionItem[];
  approvalQueue: LiveBrokerDecisionItem[];
  releasedLive: LiveBrokerDecisionItem[];
  liveMirrors: LiveBrokerDecisionItem[];
  divergenceRows: LiveBrokerDecisionItem[];
};

export type PaperLiveOutcomeSummary = {
  liveCandidates: number;
  releasedLive: number;
  blockedLive: number;
  mirrorEligible: number;
  divergenceCount: number;
  liveFills: number;
  /** Zeilen aus GET /v1/paper/trades/recent (Fenster). */
  paperTradeRowsLoaded: number;
  /** Nur geschlossene Evaluationszeilen (closed_ts_ms + pnl_net_usdt) — vergleichbar mit Paper-Performance. */
  paperClosedTrades: number;
  paperWins: number;
  paperLosses: number;
};

/** Paper-Trade zählt für Shadow/Live-Vergleich nur mit Abschluss und bewertetem PnL. */
export function paperTradeRowIsClosedEvaluated(trade: PaperTradeRow): boolean {
  return trade.closed_ts_ms != null && trade.pnl_net_usdt != null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function payloadText(item: AlertOutboxItem, key: string): string | null {
  const payload = asRecord(item.payload);
  const value = payload?.[key];
  if (typeof value === "string" && value.trim()) return value.trim();
  if (typeof value === "number") return String(value);
  return null;
}

export function matchAlertToDecision(
  decision: LiveBrokerDecisionItem,
  alerts: readonly AlertOutboxItem[],
): AlertOutboxItem | null {
  const execCorrelation = `exec:${decision.execution_id}`;
  for (const alert of alerts) {
    const executionId = payloadText(alert, "execution_id");
    const signalId = payloadText(alert, "signal_id");
    const correlationId = payloadText(alert, "correlation_id");
    if (executionId === decision.execution_id) return alert;
    if (decision.source_signal_id && signalId === decision.source_signal_id)
      return alert;
    if (correlationId === execCorrelation) return alert;
  }
  return null;
}

function hasViolations(value: unknown): boolean {
  return Array.isArray(value) && value.length > 0;
}

export function buildDecisionBuckets(
  decisions: readonly LiveBrokerDecisionItem[],
): DecisionBuckets {
  const planQueue = decisions.filter(
    (decision) =>
      decision.decision_action === "live_candidate_recorded" ||
      decision.decision_action === "shadow_recorded" ||
      decision.decision_action === "blocked",
  );
  const approvalQueue = decisions.filter(
    (decision) =>
      decision.effective_runtime_mode === "live" &&
      decision.decision_action === "live_candidate_recorded" &&
      !decision.operator_release_exists,
  );
  const releasedLive = decisions.filter(
    (decision) =>
      decision.effective_runtime_mode === "live" &&
      decision.operator_release_exists === true,
  );
  const liveMirrors = decisions.filter(
    (decision) =>
      decision.live_mirror_eligible === true ||
      decision.operator_release_exists === true,
  );
  const divergenceRows = decisions.filter(
    (decision) =>
      decision.shadow_live_match_ok === false ||
      hasViolations(decision.shadow_live_hard_violations) ||
      hasViolations(decision.shadow_live_soft_violations),
  );
  return {
    planQueue,
    approvalQueue,
    releasedLive,
    liveMirrors,
    divergenceRows,
  };
}

export function summarizePaperVsLiveOutcome(input: {
  decisions: readonly LiveBrokerDecisionItem[];
  fills: readonly LiveBrokerFillItem[];
  paperTrades: readonly PaperTradeRow[];
}): PaperLiveOutcomeSummary {
  const buckets = buildDecisionBuckets(input.decisions);
  const paperClosed = input.paperTrades.filter(paperTradeRowIsClosedEvaluated);
  const paperWins = paperClosed.filter(
    (trade) => (trade.pnl_net_usdt ?? 0) > 0,
  ).length;
  const paperLosses = paperClosed.filter(
    (trade) => (trade.pnl_net_usdt ?? 0) < 0,
  ).length;
  return {
    liveCandidates: input.decisions.filter(
      (decision) => decision.decision_action === "live_candidate_recorded",
    ).length,
    releasedLive: buckets.releasedLive.length,
    blockedLive: input.decisions.filter(
      (decision) => decision.decision_action === "blocked",
    ).length,
    mirrorEligible: buckets.liveMirrors.length,
    divergenceCount: buckets.divergenceRows.length,
    liveFills: input.fills.length,
    paperTradeRowsLoaded: input.paperTrades.length,
    paperClosedTrades: paperClosed.length,
    paperWins,
    paperLosses,
  };
}
