/**
 * Reine Hilfen fuer Operator-Ansichten (testbar, keine Netzwerk-Seiteneffekte).
 */

export type OperatorDriftSummary = {
  totalCount: number | null;
  positionMismatchCount: number | null;
  orderLocalOnly: number | null;
  orderExchangeOnly: number | null;
};

export type OperatorAccountRow = {
  label: string;
  value: string;
};

/** Kompakte Lage fuer Operator-Leiste (keine React-/API-Imports). */
export type OperatorSituationSummary = {
  executionMode: string;
  strategyMode: string;
  liveTradeEnable: boolean;
  liveSubmissionEnabled: boolean;
  killSwitchActiveCount: number;
  safetyLatchActive: boolean;
  onlineDriftAction: string | null;
  onlineDriftComputedAt: string | null;
  openMonitorAlerts: number;
  brokerServiceName: string | null;
  brokerServiceStatus: string | null;
  reconcileStatus: string | null;
  databaseOk: boolean;
  recentDriftEventCount: number;
};

export function findBrokerishService(
  services: ReadonlyArray<{ name: string; status: string }>,
): { name: string; status: string } | null {
  const n = (s: string) => s.toLowerCase();
  const hit =
    services.find((s) => {
      const x = n(s.name);
      return (
        x.includes("live-broker") ||
        x.includes("live_broker") ||
        x.includes("paper-broker")
      );
    }) ?? services.find((s) => n(s.name).includes("broker"));
  return hit ? { name: hit.name, status: hit.status } : null;
}

export function buildOperatorSituationSummary(input: {
  health: {
    execution: {
      execution_mode: string;
      strategy_execution_mode: string;
      live_trade_enable: boolean;
      live_order_submission_enabled: boolean;
    };
    database: string;
    services: ReadonlyArray<{ name: string; status: string }>;
    ops: {
      live_broker: {
        latest_reconcile_status?: string | null;
        safety_latch_active?: boolean;
      };
    };
  } | null;
  killSwitchActiveCount: number;
  onlineDrift: {
    effective_action?: string;
    computed_at?: string | null;
  } | null;
  openMonitorAlerts: number;
  recentDriftItemsCount: number;
}): OperatorSituationSummary {
  const h = input.health;
  const broker = h ? findBrokerishService(h.services) : null;
  return {
    executionMode: h?.execution.execution_mode ?? "—",
    strategyMode: h?.execution.strategy_execution_mode ?? "—",
    liveTradeEnable: Boolean(h?.execution.live_trade_enable),
    liveSubmissionEnabled: Boolean(h?.execution.live_order_submission_enabled),
    killSwitchActiveCount: input.killSwitchActiveCount,
    safetyLatchActive: Boolean(h?.ops.live_broker.safety_latch_active),
    onlineDriftAction: input.onlineDrift?.effective_action?.trim() ?? null,
    onlineDriftComputedAt: input.onlineDrift?.computed_at ?? null,
    openMonitorAlerts: input.openMonitorAlerts,
    brokerServiceName: broker?.name ?? null,
    brokerServiceStatus: broker?.status ?? null,
    reconcileStatus: h?.ops.live_broker.latest_reconcile_status ?? null,
    databaseOk: (h?.database ?? "").toLowerCase() === "ok",
    recentDriftEventCount: input.recentDriftItemsCount,
  };
}

function asRecord(v: unknown): Record<string, unknown> | null {
  return v !== null && typeof v === "object" && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : null;
}

/** Extrahiert Drift-Zahlen aus live-broker reconcile details_json. */
export function parseDriftFromRuntimeDetails(
  details: unknown,
): OperatorDriftSummary {
  const d = asRecord(details);
  const drift = d ? asRecord(d.drift) : null;
  const order = drift ? asRecord(drift.order) : null;
  const positions = drift ? asRecord(drift.positions) : null;
  const tc = drift?.total_count;
  return {
    totalCount: typeof tc === "number" ? tc : null,
    positionMismatchCount:
      typeof positions?.mismatch_count === "number"
        ? positions.mismatch_count
        : null,
    orderLocalOnly:
      typeof order?.local_only_count === "number"
        ? order.local_only_count
        : null,
    orderExchangeOnly:
      typeof order?.exchange_only_count === "number"
        ? order.exchange_only_count
        : null,
  };
}

const ACCOUNT_KEYS_PRIORITY = [
  "marginRatio",
  "crossedMarginRiskRatio",
  "available",
  "availableBalance",
  "accountEquity",
  "equity",
  "usedMargin",
  "crossedRiskRate",
  "isolatedLongLeverage",
  "isolatedShortLeverage",
];

/** Zeilen aus exchange account snapshot raw_data (Bitget-artige Keys, generisch). */
export function extractAccountDisplayRows(
  details: unknown,
  maxRows = 10,
): OperatorAccountRow[] {
  const d = asRecord(details);
  const recovery = d ? asRecord(d.recovery_state) : null;
  const snaps = recovery?.exchange_account_snapshots;
  if (!Array.isArray(snaps) || snaps.length === 0) return [];
  const first = asRecord(snaps[0]);
  const raw = first ? asRecord(first.raw_data) : null;
  if (!raw) return [];
  const rows: OperatorAccountRow[] = [];
  const seen = new Set<string>();
  for (const k of ACCOUNT_KEYS_PRIORITY) {
    if (k in raw && rows.length < maxRows) {
      const val = raw[k];
      rows.push({ label: k, value: formatScalar(val) });
      seen.add(k);
    }
  }
  for (const [k, val] of Object.entries(raw)) {
    if (rows.length >= maxRows) break;
    if (seen.has(k)) continue;
    seen.add(k);
    rows.push({ label: k, value: formatScalar(val) });
  }
  return rows.slice(0, maxRows);
}

function formatScalar(val: unknown): string {
  if (val === null || val === undefined) return "—";
  if (
    typeof val === "string" ||
    typeof val === "number" ||
    typeof val === "boolean"
  ) {
    return String(val);
  }
  try {
    return JSON.stringify(val).slice(0, 120);
  } catch {
    return "[object]";
  }
}

/** Liquidations-/Margin-Hinweise aus Paper-Positions-meta (falls vorhanden). */
export function extractPaperPositionRiskRows(
  metas: ReadonlyArray<Record<string, unknown>>,
  maxPerPosition = 4,
): OperatorAccountRow[] {
  const keys = [
    "liquidation_price",
    "liq_price",
    "distance_to_liquidation_pct",
    "liquidation_buffer_bps",
    "isolated_margin",
    "used_margin_after",
    "projected_margin_usage_pct",
  ];
  const out: OperatorAccountRow[] = [];
  metas.forEach((meta, idx) => {
    let n = 0;
    for (const k of keys) {
      if (n >= maxPerPosition) break;
      if (k in meta) {
        out.push({ label: `pos${idx + 1}.${k}`, value: formatScalar(meta[k]) });
        n += 1;
      }
    }
  });
  return out;
}
