import type {
  LiveBrokerDecisionItem,
  LiveBrokerOrderItem,
  LiveBrokerRuntimeItem,
  LiveSignal,
  MarketUniverseInstrumentItem,
  SignalRecentItem,
  SystemHealthResponse,
} from "@/lib/types";

export type RiskOverallStatus = "ok" | "warnung" | "blockiert";

export type AssetRiskRow = {
  symbol: string;
  riskTier: string;
  volatilityAtr: string;
  spreadLiquidity: string;
  fundingOi: string;
  dataQuality: string;
  maxMode: string;
  blockReasons: string[];
};

const BLOCKER_LABELS: Array<[RegExp, string]> = [
  [/stale|veraltet/i, "stale data"],
  [/exchange.*truth|truth.*missing|reconcile.*missing/i, "no exchange truth"],
  [/safety[_ -]?latch|latch/i, "safety latch"],
  [/kill[_ -]?switch|kill switch/i, "kill switch"],
  [/margin.*exceed|margin_utilization_exceeded/i, "margin exceeded"],
  [/drawdown|daily_loss|weekly_loss|loss_streak/i, "max drawdown"],
  [/quarant|suspend|delist/i, "asset quarantined"],
];

function asNum(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function mapReason(reason: string): string {
  for (const [re, label] of BLOCKER_LABELS) {
    if (re.test(reason)) return label;
  }
  return reason;
}

function toReasons(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const out = value
    .map((item) => {
      if (typeof item === "string") return item.trim();
      if (item && typeof item === "object" && !Array.isArray(item)) {
        const o = item as Record<string, unknown>;
        const candidate = o.reason ?? o.message ?? o.code;
        return typeof candidate === "string" ? candidate.trim() : "";
      }
      return "";
    })
    .filter(Boolean)
    .map(mapReason);
  return Array.from(new Set(out));
}

export function computeRiskOverviewFromRuntime(
  runtime: LiveBrokerRuntimeItem | null | undefined,
): {
  dailyLoss: string;
  weeklyLoss: string;
  drawdown: string;
  marginUsage: string;
  portfolioExposure: string;
  topRisks: string[];
} {
  const details = asRecord(runtime?.details);
  const acct = asRecord(details.risk_account_snapshot);
  const daily = asNum(acct.daily_realized_loss_usdt);
  const weekly = asNum(acct.weekly_realized_loss_usdt);
  const dd = asNum(acct.account_drawdown_0_1);
  const margin = asNum(acct.margin_utilization_0_1);
  const exposure = asNum(acct.gross_exposure_ratio_0_1);
  const topRiskRaw = acct.top_risks_json;
  const topRisks = Array.isArray(topRiskRaw)
    ? topRiskRaw
        .map((x) => (typeof x === "string" ? x : ""))
        .filter(Boolean)
        .slice(0, 4)
    : [];
  return {
    dailyLoss: daily == null ? "—" : `${daily.toFixed(2)} USDT`,
    weeklyLoss: weekly == null ? "—" : `${weekly.toFixed(2)} USDT`,
    drawdown: dd == null ? "—" : `${(dd * 100).toFixed(1)}%`,
    marginUsage: margin == null ? "—" : `${(margin * 100).toFixed(1)}%`,
    portfolioExposure: exposure == null ? "—" : `${(exposure * 100).toFixed(1)}%`,
    topRisks,
  };
}

export function computeLiveBlockers(params: {
  health: SystemHealthResponse | null;
  runtime: LiveBrokerRuntimeItem | null | undefined;
  liveSignal: LiveSignal | null | undefined;
  killSwitchCount: number;
  decisions: readonly LiveBrokerDecisionItem[];
}): string[] {
  const blockers: string[] = [];
  const { health, runtime, liveSignal, killSwitchCount, decisions } = params;
  if (!liveSignal) blockers.push("stale data");
  blockers.push(...toReasons(liveSignal?.live_execution_block_reasons_json));
  blockers.push(...toReasons(liveSignal?.governor_universal_hard_block_reasons_json));
  if ((runtime?.safety_latch_active ?? false) === true) blockers.push("safety latch");
  if (killSwitchCount > 0) blockers.push("kill switch");
  const details = asRecord(runtime?.details);
  const acct = asRecord(details.risk_account_snapshot);
  const margin = asNum(acct.margin_utilization_0_1);
  if (margin != null && margin > 0.9) blockers.push("margin exceeded");
  const dd = asNum(acct.account_drawdown_0_1);
  if (dd != null && dd > 0.2) blockers.push("max drawdown");
  if (health?.ops?.live_broker?.latest_reconcile_status == null) {
    blockers.push("no exchange truth");
  }
  if (decisions.some((d) => (d.risk_primary_reason ?? "").toLowerCase().includes("quarant"))) {
    blockers.push("asset quarantined");
  }
  return Array.from(new Set(blockers));
}

export function computeOverallStatus(blockers: readonly string[]): RiskOverallStatus {
  if (blockers.length > 0) return "blockiert";
  return "ok";
}

function riskTierFromSignal(signal: SignalRecentItem | undefined): string {
  const direct = (signal as unknown as Record<string, unknown> | undefined)?.asset_risk_tier;
  if (typeof direct === "string" && direct.trim()) return direct.trim();
  const metadata = asRecord(signal?.signal_view);
  const fromMeta = metadata.asset_risk_tier;
  if (typeof fromMeta === "string" && fromMeta.trim()) return fromMeta.trim();
  const reasons = toReasons(signal?.live_execution_block_reasons_json);
  if (reasons.some((r) => r.includes("asset quarantined"))) return "Tier 5";
  if (reasons.length > 0) return "Tier 4";
  return "Tier 2";
}

function maxMode(signal: SignalRecentItem | undefined): string {
  if (!signal) return "Paper";
  const tier = riskTierFromSignal(signal).toLowerCase();
  if (tier.includes("tier 4") || tier.includes("tier 5")) return "Paper";
  const action = (signal.trade_action ?? "").toLowerCase();
  if (action === "allow_trade" && signal.live_execution_clear_for_real_money) return "Live";
  if (action === "do_not_trade" || action === "blocked") return "Paper";
  return "Shadow";
}

export function buildAssetRiskRows(params: {
  instruments: readonly MarketUniverseInstrumentItem[];
  signals: readonly SignalRecentItem[];
}): AssetRiskRow[] {
  const signalMap = new Map(params.signals.map((s) => [s.symbol, s]));
  return params.instruments.slice(0, 40).map((inst) => {
    const signal = signalMap.get(inst.symbol);
    const spread = asNum(inst.raw_metadata?.spread_bps);
    const liquidity = asNum(inst.raw_metadata?.depth_to_bar_volume_ratio);
    const signalView = asRecord(signal?.signal_view);
    const atr = asNum(signalView.atrp_14);
    const funding = asNum(inst.raw_metadata?.funding_rate_bps);
    const oi = asNum(inst.raw_metadata?.open_interest_change_pct);
    const reasons = toReasons(signal?.live_execution_block_reasons_json);
    const tier = riskTierFromSignal(signal);
    const tierBlocked = tier.toLowerCase().includes("tier 4") || tier.toLowerCase().includes("tier 5");
    const rowReasons = [...reasons];
    if (tierBlocked) rowReasons.push("asset quarantined");
    return {
      symbol: inst.symbol,
      riskTier: tier,
      volatilityAtr: atr == null ? "—" : `ATR ${(atr * 100).toFixed(2)}%`,
      spreadLiquidity: `Spread ${spread == null ? "—" : `${spread.toFixed(1)} bps`} · Liq ${liquidity == null ? "—" : liquidity.toFixed(2)}`,
      fundingOi:
        inst.market_family === "futures"
          ? `Funding ${funding == null ? "—" : `${funding.toFixed(1)} bps`} · OI ${oi == null ? "—" : `${oi.toFixed(1)}%`}`
          : "n/a",
      dataQuality: inst.metadata_verified ? "ok" : "warnung",
      maxMode: maxMode(signal),
      blockReasons: rowReasons.length > 0 ? Array.from(new Set(rowReasons)) : ["Keine harten Blocker gemeldet."],
    };
  });
}

export function portfolioRiskSummary(params: {
  runtime: LiveBrokerRuntimeItem | null | undefined;
  decisions: readonly LiveBrokerDecisionItem[];
  orders: readonly LiveBrokerOrderItem[];
}) {
  const details = asRecord(params.runtime?.details);
  const acct = asRecord(details.risk_account_snapshot);
  const pr = asRecord(acct.portfolio_risk_json);
  const familyExposure = asRecord(pr.family_exposure_fraction_0_1);
  const directionExposure = asNum(pr.direction_net_exposure_0_1);
  const cluster = asNum(pr.correlated_cluster_largest_exposure_0_1);
  const pendingMirrorTrades = asNum(pr.pending_mirror_trades_count) ?? 0;
  const openOrdersNotional = asNum(pr.open_orders_notional_to_equity_0_1);
  const liveBlockReasons = toReasons(pr.live_block_reasons_json);
  if (liveBlockReasons.length === 0 && params.decisions.length === 0) {
    liveBlockReasons.push("stale data");
  }
  return {
    familyExposure,
    directionExposure,
    cluster,
    pendingMirrorTrades,
    openOrdersNotional,
    liveBlockReasons,
    openOrdersCount: params.orders.length,
  };
}
