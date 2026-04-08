import {
  buildDecisionBuckets,
  matchAlertToDecision,
  summarizePaperVsLiveOutcome,
} from "@/lib/operator-console";
import type {
  AlertOutboxItem,
  LiveBrokerDecisionItem,
  LiveBrokerFillItem,
  PaperTradeRow,
} from "@/lib/types";

function mkDecision(
  overrides: Partial<LiveBrokerDecisionItem>,
): LiveBrokerDecisionItem {
  return {
    execution_id: "exec-1",
    source_service: "live-broker",
    source_signal_id: "sig-1",
    symbol: "BTCUSDT",
    signal_market_family: "futures",
    signal_playbook_id: "pb-1",
    signal_meta_trade_lane: "paper_default",
    signal_canonical_instrument_id: "bitget:futures:linear:BTCUSDT",
    live_mirror_eligible: false,
    timeframe: "5m",
    direction: "long",
    requested_runtime_mode: "live",
    effective_runtime_mode: "live",
    decision_action: "live_candidate_recorded",
    decision_reason: "candidate_ready",
    order_type: "market",
    leverage: 7,
    signal_allowed_leverage: 7,
    signal_recommended_leverage: 7,
    signal_trade_action: "allow_trade",
    signal_leverage_policy_version: "v1",
    signal_leverage_cap_reasons_json: [],
    approved_7x: true,
    qty_base: "0.1",
    entry_price: "50000",
    stop_loss: "49500",
    take_profit: "51000",
    operator_release_exists: false,
    operator_release_source: null,
    operator_release_ts: null,
    risk_trade_action: "allow_trade",
    risk_decision_state: "accepted",
    risk_primary_reason: null,
    risk_reasons_json: [],
    shadow_live_match_ok: true,
    shadow_live_hard_violations: [],
    shadow_live_soft_violations: [],
    payload: {},
    trace: {},
    created_ts: "2026-03-30T00:00:00Z",
    updated_ts: "2026-03-30T00:00:01Z",
    ...overrides,
  };
}

function mkAlert(overrides: Partial<AlertOutboxItem>): AlertOutboxItem {
  return {
    alert_id: "alert-1",
    created_ts: "2026-03-30T00:00:00Z",
    alert_type: "OPERATOR_PLAN_SUMMARY",
    severity: "info",
    symbol: "BTCUSDT",
    timeframe: "5m",
    dedupe_key: null,
    chat_id: 1,
    state: "sent",
    attempt_count: 1,
    last_error: null,
    telegram_message_id: 999,
    sent_ts: "2026-03-30T00:00:01Z",
    payload: {},
    ...overrides,
  };
}

describe("operator-console", () => {
  it("matches alerts by execution_id and signal_id", () => {
    const decision = mkDecision({
      execution_id: "exec-42",
      source_signal_id: "sig-42",
    });
    const alert = mkAlert({
      payload: { execution_id: "exec-42", signal_id: "sig-42" },
    });
    expect(matchAlertToDecision(decision, [alert])?.alert_id).toBe("alert-1");
  });

  it("matches alerts by correlation_id fallback", () => {
    const decision = mkDecision({ execution_id: "exec-corr" });
    const alert = mkAlert({
      payload: { correlation_id: "exec:exec-corr" },
    });
    expect(matchAlertToDecision(decision, [alert])?.alert_id).toBe("alert-1");
  });

  it("returns null when no alert matches", () => {
    const decision = mkDecision({
      execution_id: "exec-none",
      source_signal_id: "sig-none",
    });
    expect(
      matchAlertToDecision(decision, [mkAlert({ payload: {} })]),
    ).toBeNull();
  });

  it("matches numeric execution ids and ignores non-object payloads safely", () => {
    const decision = mkDecision({ execution_id: "42" });
    const numericAlert = mkAlert({ payload: { execution_id: 42 } });
    const textAlert = mkAlert({
      payload: "not-an-object" as unknown as Record<string, unknown>,
    });
    expect(
      matchAlertToDecision(decision, [textAlert, numericAlert])?.alert_id,
    ).toBe("alert-1");
  });

  it("builds approval, release, mirror and divergence buckets", () => {
    const decisions = [
      mkDecision({ execution_id: "exec-a", operator_release_exists: false }),
      mkDecision({
        execution_id: "exec-b",
        operator_release_exists: true,
        live_mirror_eligible: true,
      }),
      mkDecision({
        execution_id: "exec-c",
        decision_action: "blocked",
        shadow_live_match_ok: false,
        shadow_live_hard_violations: ["shadow_gap"],
      }),
    ];
    const buckets = buildDecisionBuckets(decisions);
    expect(buckets.planQueue).toHaveLength(3);
    expect(buckets.approvalQueue).toHaveLength(1);
    expect(buckets.releasedLive).toHaveLength(1);
    expect(buckets.liveMirrors).toHaveLength(1);
    expect(buckets.divergenceRows).toHaveLength(1);
  });

  it("keeps empty buckets when no decisions qualify", () => {
    const buckets = buildDecisionBuckets([
      mkDecision({
        execution_id: "exec-shadow",
        effective_runtime_mode: "shadow",
        decision_action: "shadow_recorded",
        live_mirror_eligible: false,
        shadow_live_match_ok: true,
      }),
    ]);
    expect(buckets.approvalQueue).toHaveLength(0);
    expect(buckets.releasedLive).toHaveLength(0);
    expect(buckets.divergenceRows).toHaveLength(0);
  });

  it("summarizes paper-vs-live outcome windows", () => {
    const decisions = [
      mkDecision({
        decision_action: "live_candidate_recorded",
        operator_release_exists: true,
      }),
      mkDecision({ decision_action: "blocked" }),
    ];
    const fills: LiveBrokerFillItem[] = [
      {
        internal_order_id: "ord-1",
        exchange_order_id: "ex-1",
        exchange_trade_id: "trade-1",
        symbol: "BTCUSDT",
        side: "buy",
        price: "50000",
        size: "0.1",
        fee: "1",
        fee_coin: "USDT",
        is_maker: false,
        exchange_ts_ms: 1,
        raw: {},
        created_ts: "2026-03-30T00:00:00Z",
      },
    ];
    const paperTrades: PaperTradeRow[] = [
      {
        position_id: "pos-1",
        symbol: "BTCUSDT",
        side: "long",
        qty_base: "0.1",
        entry_price_avg: "50000",
        closed_ts_ms: 1,
        state: "closed",
        pnl_net_usdt: 12,
        fees_total_usdt: 1,
        funding_total_usdt: 0,
        direction_correct: true,
        reason_closed: "tp",
        leverage_allocator: null,
        meta: {},
      },
      {
        position_id: "pos-2",
        symbol: "ETHUSDT",
        side: "short",
        qty_base: "0.2",
        entry_price_avg: "3000",
        closed_ts_ms: 2,
        state: "closed",
        pnl_net_usdt: -5,
        fees_total_usdt: 1,
        funding_total_usdt: 0,
        direction_correct: false,
        reason_closed: "stop",
        leverage_allocator: null,
        meta: {},
      },
      {
        position_id: "pos-open",
        symbol: "BTCUSDT",
        side: "long",
        qty_base: "0.05",
        entry_price_avg: "51000",
        closed_ts_ms: null,
        state: "open",
        pnl_net_usdt: null,
        fees_total_usdt: null,
        funding_total_usdt: null,
        direction_correct: null,
        reason_closed: null,
        leverage_allocator: null,
        meta: {},
      },
    ];
    const summary = summarizePaperVsLiveOutcome({
      decisions,
      fills,
      paperTrades,
    });
    expect(summary.liveCandidates).toBe(1);
    expect(summary.releasedLive).toBe(1);
    expect(summary.blockedLive).toBe(1);
    expect(summary.liveFills).toBe(1);
    expect(summary.paperTradeRowsLoaded).toBe(3);
    expect(summary.paperClosedTrades).toBe(2);
    expect(summary.paperWins).toBe(1);
    expect(summary.paperLosses).toBe(1);
  });
});
