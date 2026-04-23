/**
 * Deterministische Kurzbegruendungen aus Signal-Persistenz (keine LLM-Inferenz).
 * Alle Nutzersicht-Strings ueber pages.signalsDetail.rationale* (i18n).
 */

import { formatDistancePctField, formatNum } from "@/lib/format";
import type { TranslateFn } from "@/lib/user-facing-fetch-error";

export type SignalRationaleInput = {
  trade_action?: string | null;
  decision_state?: string | null;
  market_family?: string | null;
  meta_trade_lane?: string | null;
  abstention_reasons_json?: unknown;
  rejection_reasons_json?: unknown;
  leverage_cap_reasons_json?: unknown;
  governor_universal_hard_block_reasons_json?: unknown;
  live_execution_block_reasons_json?: unknown;
  live_execution_clear_for_real_money?: boolean;
  model_ood_alert?: boolean;
  model_uncertainty_0_1?: number | null;
  uncertainty_effective_for_leverage_0_1?: number | null;
  recommended_leverage?: number | null;
  allowed_leverage?: number | null;
  stop_fragility_0_1?: number | null;
  stop_executability_0_1?: number | null;
  stop_budget_max_pct_allowed?: number | null;
  stop_distance_pct?: number | null;
  stop_min_executable_pct?: number | null;
  exit_family_effective_primary?: string | null;
  exit_family_primary_ensemble?: string | null;
  specialist_router_id?: string | null;
  router_selected_playbook_id?: string | null;
  router_operator_gate_required?: boolean | null;
  playbook_id?: string | null;
  playbook_family?: string | null;
  regime_state?: string | null;
  shadow_divergence_0_1?: number | null;
  instrument_metadata_verified?: boolean | null;
  instrument_product_type?: string | null;
  instrument_margin_account_mode?: string | null;
  instrument_supports_long_short?: boolean | null;
  instrument_supports_reduce_only?: boolean | null;
  instrument_supports_leverage?: boolean | null;
  latest_execution_decision_action?: string | null;
  latest_execution_runtime_mode?: string | null;
  operator_release_exists?: boolean;
  live_mirror_eligible?: boolean | null;
  telegram_alert_type?: string | null;
  telegram_delivery_state?: string | null;
};

function asStringArray(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v
    .map((x) => (typeof x === "string" ? x : JSON.stringify(x)))
    .filter(Boolean);
}

function tNo(
  t: TranslateFn,
  key: string,
  vars?: Record<string, string | number | boolean>,
) {
  return t(`pages.signalsDetail.rationaleNo.${key}`, vars);
}

function tTr(
  t: TranslateFn,
  key: string,
  vars?: Record<string, string | number | boolean>,
) {
  return t(`pages.signalsDetail.rationaleTrade.${key}`, vars);
}

export function summarizeNoTradeReasons(
  s: SignalRationaleInput,
  t: TranslateFn,
): string[] {
  const lines: string[] = [];
  const ta = (s.trade_action ?? "").toLowerCase();
  if (ta === "do_not_trade" || ta === "no_trade" || ta === "abstain") {
    lines.push(
      tNo(t, "hybridTradeAction", {
        action: s.trade_action ?? "—",
      }),
    );
  }
  const abs = asStringArray(s.abstention_reasons_json);
  for (const x of abs.slice(0, 8)) lines.push(tNo(t, "abstention", { detail: x }));
  const rej = asStringArray(s.rejection_reasons_json);
  for (const x of rej.slice(0, 8)) lines.push(tNo(t, "rejection", { detail: x }));
  const uni = asStringArray(s.governor_universal_hard_block_reasons_json);
  for (const x of uni.slice(0, 8))
    lines.push(tNo(t, "governorUniversal", { detail: x }));
  if (s.model_ood_alert) {
    lines.push(tNo(t, "oodAlert"));
  }
  if (
    typeof s.model_uncertainty_0_1 === "number" &&
    s.model_uncertainty_0_1 >= 0.55
  ) {
    lines.push(
      tNo(t, "highUncertainty", {
        pct: (s.model_uncertainty_0_1 * 100).toFixed(0),
      }),
    );
  }
  const lev = asStringArray(s.leverage_cap_reasons_json);
  for (const x of lev.slice(0, 6)) lines.push(tNo(t, "leverageCap", { detail: x }));
  if (
    typeof s.stop_fragility_0_1 === "number" &&
    s.stop_fragility_0_1 >= 0.65 &&
    typeof s.stop_executability_0_1 === "number" &&
    s.stop_executability_0_1 <= 0.45
  ) {
    lines.push(
      tNo(t, "stopFragility", {
        frag: s.stop_fragility_0_1.toFixed(2),
        exec: s.stop_executability_0_1.toFixed(2),
      }),
    );
  }
  if (
    typeof s.stop_distance_pct === "number" &&
    typeof s.stop_budget_max_pct_allowed === "number" &&
    s.stop_distance_pct > s.stop_budget_max_pct_allowed
  ) {
    lines.push(
      tNo(t, "stopOverBudget", {
        dist: formatDistancePctField(s.stop_distance_pct),
        cap: formatDistancePctField(s.stop_budget_max_pct_allowed),
      }),
    );
  }
  if (
    typeof s.stop_distance_pct === "number" &&
    typeof s.stop_min_executable_pct === "number" &&
    s.stop_distance_pct < s.stop_min_executable_pct
  ) {
    lines.push(
      tNo(t, "stopUnderMin", {
        dist: formatDistancePctField(s.stop_distance_pct),
        min: formatDistancePctField(s.stop_min_executable_pct),
      }),
    );
  }
  if (s.instrument_metadata_verified === false) {
    lines.push(tNo(t, "metadataUnverified"));
  }
  if (
    s.instrument_supports_long_short === false &&
    (s.market_family ?? "").toLowerCase() === "spot"
  ) {
    lines.push(tNo(t, "spotNoShort"));
  }
  if (s.live_mirror_eligible === false) {
    lines.push(tNo(t, "notLiveMirrorEligible"));
  }
  if (s.latest_execution_decision_action === "blocked") {
    lines.push(
      tNo(t, "liveBrokerBlocked", {
        mode: s.latest_execution_runtime_mode ?? "—",
      }),
    );
  }
  if (lines.length === 0 && ta !== "allow_trade") {
    lines.push(tNo(t, "fallbackNoBranch"));
  }
  return lines;
}

export function summarizeTradeRationale(
  s: SignalRationaleInput,
  t: TranslateFn,
): string[] {
  const lines: string[] = [];
  const ta = (s.trade_action ?? "").toLowerCase();
  if (ta === "allow_trade") {
    lines.push(
      tTr(t, "allowTradeLine", {
        state: s.decision_state ?? "—",
      }),
    );
  } else {
    return lines;
  }
  if (s.meta_trade_lane) lines.push(tTr(t, "lane", { lane: s.meta_trade_lane }));
  if (s.market_family) lines.push(tTr(t, "marketFamily", { family: s.market_family }));
  if (s.instrument_product_type || s.instrument_margin_account_mode) {
    lines.push(
      tTr(t, "instrumentContext", {
        product: s.instrument_product_type ?? "—",
        margin: s.instrument_margin_account_mode ?? "—",
      }),
    );
  }
  if (s.playbook_family || s.playbook_id) {
    lines.push(
      tTr(t, "playbook", {
        id: s.playbook_id ?? "—",
        family: s.playbook_family ?? "—",
      }),
    );
  }
  if (s.regime_state) lines.push(tTr(t, "regime", { state: s.regime_state }));
  if (s.specialist_router_id)
    lines.push(tTr(t, "router", { id: s.specialist_router_id }));
  if (s.router_selected_playbook_id)
    lines.push(
      tTr(t, "routerPlaybook", { id: s.router_selected_playbook_id }),
    );
  if (s.router_operator_gate_required === true) {
    lines.push(tTr(t, "operatorGate"));
  }
  if (s.exit_family_effective_primary || s.exit_family_primary_ensemble) {
    lines.push(
      tTr(t, "exitFamily", {
        primary: s.exit_family_effective_primary ?? "—",
        ensemble: s.exit_family_primary_ensemble ?? "—",
      }),
    );
  }
  if (
    typeof s.allowed_leverage === "number" ||
    typeof s.recommended_leverage === "number"
  ) {
    const rec =
      s.recommended_leverage == null
        ? "—"
        : `${formatNum(s.recommended_leverage, 0)}×`;
    const allow =
      s.allowed_leverage == null
        ? "—"
        : `${formatNum(s.allowed_leverage, 0)}×`;
    lines.push(tTr(t, "leverage", { rec, allow }));
  }
  if (
    typeof s.stop_fragility_0_1 === "number" ||
    typeof s.stop_executability_0_1 === "number"
  ) {
    lines.push(
      tTr(t, "stopFragExec", {
        frag: s.stop_fragility_0_1?.toFixed(2) ?? "—",
        exec: s.stop_executability_0_1?.toFixed(2) ?? "—",
      }),
    );
  }
  const lev = asStringArray(s.leverage_cap_reasons_json);
  if (lev.length)
    lines.push(
      tTr(t, "leverageRationale", {
        list: lev.slice(0, 4).join("; "),
      }),
    );
  if (
    typeof s.stop_distance_pct === "number" ||
    typeof s.stop_budget_max_pct_allowed === "number"
  ) {
    lines.push(
      tTr(t, "stopBudget", {
        dist: formatDistancePctField(s.stop_distance_pct ?? null),
        cap: formatDistancePctField(s.stop_budget_max_pct_allowed ?? null),
      }),
    );
  }
  if (typeof s.shadow_divergence_0_1 === "number") {
    lines.push(
      tTr(t, "shadowDiv", {
        pct: (s.shadow_divergence_0_1 * 100).toFixed(1),
      }),
    );
  }
  if (s.live_mirror_eligible === true) {
    lines.push(tTr(t, "liveMirrorEligible"));
  }
  if (s.latest_execution_decision_action) {
    lines.push(
      tTr(t, "lastExecution", {
        action: s.latest_execution_decision_action,
        mode: s.latest_execution_runtime_mode ?? "—",
      }),
    );
  }
  if (s.operator_release_exists) {
    lines.push(tTr(t, "operatorRelease"));
  }
  if (s.telegram_alert_type || s.telegram_delivery_state) {
    lines.push(
      tTr(t, "telegram", {
        type: s.telegram_alert_type ?? "—",
        state: s.telegram_delivery_state ?? "—",
      }),
    );
  }
  const liveBlocks = asStringArray(s.live_execution_block_reasons_json);
  if (liveBlocks.length) {
    lines.push(tTr(t, "liveBlockedHint"));
    for (const x of liveBlocks.slice(0, 4))
      lines.push(tTr(t, "liveBlockItem", { detail: x }));
  } else if (s.live_execution_clear_for_real_money === true) {
    lines.push(tTr(t, "governorClear"));
  }
  return lines;
}
