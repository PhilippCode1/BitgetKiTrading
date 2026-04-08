/**
 * Deterministische Kurzbegruendungen aus Signal-Persistenz (keine LLM-Inferenz).
 */

import { formatDistancePctField } from "@/lib/format";

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

export function summarizeNoTradeReasons(s: SignalRationaleInput): string[] {
  const lines: string[] = [];
  const ta = (s.trade_action ?? "").toLowerCase();
  if (ta === "do_not_trade" || ta === "no_trade" || ta === "abstain") {
    lines.push(`Hybrid trade_action=${s.trade_action ?? "—"}`);
  }
  const abs = asStringArray(s.abstention_reasons_json);
  for (const x of abs.slice(0, 8)) lines.push(`Abstention: ${x}`);
  const rej = asStringArray(s.rejection_reasons_json);
  for (const x of rej.slice(0, 8)) lines.push(`Rejection: ${x}`);
  const uni = asStringArray(s.governor_universal_hard_block_reasons_json);
  for (const x of uni.slice(0, 8))
    lines.push(`Governor (universal hard): ${x}`);
  if (s.model_ood_alert) {
    lines.push("OOD-Alert aktiv (Modell-/Datenkontext).");
  }
  if (
    typeof s.model_uncertainty_0_1 === "number" &&
    s.model_uncertainty_0_1 >= 0.55
  ) {
    lines.push(
      `Hohe Modell-Unsicherheit (${(s.model_uncertainty_0_1 * 100).toFixed(0)} %).`,
    );
  }
  const lev = asStringArray(s.leverage_cap_reasons_json);
  for (const x of lev.slice(0, 6)) lines.push(`Hebel-Cap: ${x}`);
  if (
    typeof s.stop_fragility_0_1 === "number" &&
    s.stop_fragility_0_1 >= 0.65 &&
    typeof s.stop_executability_0_1 === "number" &&
    s.stop_executability_0_1 <= 0.45
  ) {
    lines.push(
      `Stop-Fragilität hoch (${s.stop_fragility_0_1.toFixed(2)}), Ausführbarkeit niedrig (${s.stop_executability_0_1.toFixed(2)}).`,
    );
  }
  if (
    typeof s.stop_distance_pct === "number" &&
    typeof s.stop_budget_max_pct_allowed === "number" &&
    s.stop_distance_pct > s.stop_budget_max_pct_allowed
  ) {
    lines.push(
      `Stop-Distanz ${formatDistancePctField(s.stop_distance_pct)} liegt über Budget-Cap ${formatDistancePctField(s.stop_budget_max_pct_allowed)}.`,
    );
  }
  if (
    typeof s.stop_distance_pct === "number" &&
    typeof s.stop_min_executable_pct === "number" &&
    s.stop_distance_pct < s.stop_min_executable_pct
  ) {
    lines.push(
      `Stop-Distanz ${formatDistancePctField(s.stop_distance_pct)} liegt unter dem minimal ausführbaren Abstand ${formatDistancePctField(s.stop_min_executable_pct)}.`,
    );
  }
  if (s.instrument_metadata_verified === false) {
    lines.push(
      "Instrument-Metadaten nicht verifiziert; Default ist konservativ/no-trade.",
    );
  }
  if (
    s.instrument_supports_long_short === false &&
    (s.market_family ?? "").toLowerCase() === "spot"
  ) {
    lines.push(
      "Spot-Instrument ohne natives Shorting begrenzt die Trade-Richtung.",
    );
  }
  if (s.live_mirror_eligible === false) {
    lines.push(
      "Signal ist nicht live-mirror-eligible; Shadow/Paper bleibt Referenzpfad.",
    );
  }
  if (s.latest_execution_decision_action === "blocked") {
    lines.push(
      `Live-Broker blockierte die letzte Execution im Modus ${s.latest_execution_runtime_mode ?? "—"}.`,
    );
  }
  if (lines.length === 0 && ta !== "allow_trade") {
    lines.push(
      "Kein expliziter Trade-Zweig — Details in reasons_json / Explain prüfen.",
    );
  }
  return lines;
}

export function summarizeTradeRationale(s: SignalRationaleInput): string[] {
  const lines: string[] = [];
  const ta = (s.trade_action ?? "").toLowerCase();
  if (ta === "allow_trade") {
    lines.push(
      `trade_action=allow_trade, decision_state=${s.decision_state ?? "—"}`,
    );
  } else {
    return lines;
  }
  if (s.meta_trade_lane) lines.push(`Lane: ${s.meta_trade_lane}`);
  if (s.market_family) lines.push(`Markt-Familie: ${s.market_family}`);
  if (s.instrument_product_type || s.instrument_margin_account_mode) {
    lines.push(
      `Instrument-Kontext: product=${s.instrument_product_type ?? "—"} margin_mode=${s.instrument_margin_account_mode ?? "—"}`,
    );
  }
  if (s.playbook_family || s.playbook_id) {
    lines.push(
      `Playbook: ${s.playbook_id ?? "—"} (${s.playbook_family ?? "—"})`,
    );
  }
  if (s.regime_state) lines.push(`Regime-State: ${s.regime_state}`);
  if (s.specialist_router_id) lines.push(`Router: ${s.specialist_router_id}`);
  if (s.router_selected_playbook_id)
    lines.push(`Router-Playbook: ${s.router_selected_playbook_id}`);
  if (s.router_operator_gate_required === true) {
    lines.push("Operator-Gate: Freigabe erforderlich (Lane/Policy).");
  }
  if (s.exit_family_effective_primary || s.exit_family_primary_ensemble) {
    lines.push(
      `Exit-Familie effektiv: ${s.exit_family_effective_primary ?? "—"} (Ensemble: ${s.exit_family_primary_ensemble ?? "—"})`,
    );
  }
  if (
    typeof s.allowed_leverage === "number" ||
    typeof s.recommended_leverage === "number"
  ) {
    lines.push(
      `Hebel: empfohlen ${s.recommended_leverage ?? "—"}x, frei ${s.allowed_leverage ?? "—"}x`,
    );
  }
  if (
    typeof s.stop_fragility_0_1 === "number" ||
    typeof s.stop_executability_0_1 === "number"
  ) {
    lines.push(
      `Stop-Fragilität/Ausführbarkeit: ${s.stop_fragility_0_1?.toFixed(2) ?? "—"} / ${s.stop_executability_0_1?.toFixed(2) ?? "—"}`,
    );
  }
  const lev = asStringArray(s.leverage_cap_reasons_json);
  if (lev.length)
    lines.push(`Hebel-Begründung (Caps): ${lev.slice(0, 4).join("; ")}`);
  if (
    typeof s.stop_distance_pct === "number" ||
    typeof s.stop_budget_max_pct_allowed === "number"
  ) {
    lines.push(
      `Stop: Distanz ${formatDistancePctField(s.stop_distance_pct ?? null)}, Budget-Cap ${formatDistancePctField(s.stop_budget_max_pct_allowed ?? null)}`,
    );
  }
  if (typeof s.shadow_divergence_0_1 === "number") {
    lines.push(
      `Shadow-Divergenz: ${(s.shadow_divergence_0_1 * 100).toFixed(1)} %`,
    );
  }
  if (s.live_mirror_eligible === true) {
    lines.push("Execution ist live-mirror-eligible.");
  }
  if (s.latest_execution_decision_action) {
    lines.push(
      `Letzte Execution: ${s.latest_execution_decision_action} (${s.latest_execution_runtime_mode ?? "—"})`,
    );
  }
  if (s.operator_release_exists) {
    lines.push("Operator-Release liegt bereits vor.");
  }
  if (s.telegram_alert_type || s.telegram_delivery_state) {
    lines.push(
      `Telegram: ${s.telegram_alert_type ?? "—"} / ${s.telegram_delivery_state ?? "—"}`,
    );
  }
  const liveBlocks = asStringArray(s.live_execution_block_reasons_json);
  if (liveBlocks.length) {
    lines.push(
      "Hinweis: Live-Execution durch Governor blockiert (Paper/Shadow können laufen).",
    );
    for (const x of liveBlocks.slice(0, 4)) lines.push(`  Live-Block: ${x}`);
  } else if (s.live_execution_clear_for_real_money === true) {
    lines.push("Governor: keine Live-Execution-Blocker in diesem Snapshot.");
  }
  return lines;
}
