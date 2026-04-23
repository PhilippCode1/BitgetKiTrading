import en from "../../messages/en.json";
import {
  summarizeNoTradeReasons,
  summarizeTradeRationale,
} from "../signal-rationale";
import { interpolate } from "../i18n/resolve-message";

type Msg = Record<string, unknown>;

function t(
  key: string,
  vars?: Record<string, string | number | boolean>,
): string {
  const parts = key.split(".").filter(Boolean);
  let cur: unknown = en as unknown as Msg;
  for (const p of parts) {
    if (cur == null || typeof cur !== "object" || Array.isArray(cur)) {
      return key;
    }
    cur = (cur as Msg)[p];
  }
  const raw = typeof cur === "string" ? cur : key;
  return interpolate(raw, vars);
}

describe("signal-rationale (i18n via en.json)", () => {
  it("summarizeNoTradeReasons lists abstention and universal blocks", () => {
    const lines = summarizeNoTradeReasons(
      {
        trade_action: "do_not_trade",
        abstention_reasons_json: ["uncertainty_gate"],
        governor_universal_hard_block_reasons_json: ["exchange_health"],
        stop_distance_pct: 0.012,
        stop_budget_max_pct_allowed: 0.01,
        instrument_metadata_verified: false,
      },
      t,
    );
    expect(lines.some((l) => l.includes("do_not_trade"))).toBe(true);
    expect(lines.some((l) => l.toLowerCase().includes("abstention"))).toBe(
      true,
    );
    expect(lines.some((l) => l.toLowerCase().includes("governor"))).toBe(true);
    expect(lines.some((l) => l.toLowerCase().includes("budget"))).toBe(true);
    expect(lines.some((l) => l.toLowerCase().includes("metadata"))).toBe(true);
  });

  it("summarizeTradeRationale returns playbook and exit when allow_trade", () => {
    const lines = summarizeTradeRationale(
      {
        trade_action: "allow_trade",
        decision_state: "accepted",
        playbook_id: "pb1",
        playbook_family: "trend",
        market_family: "usdt_futures",
        exit_family_effective_primary: "scale_out",
        exit_family_primary_ensemble: "runner",
        specialist_router_id: "deterministic_specialist_router_v1",
        instrument_product_type: "USDT-FUTURES",
        live_mirror_eligible: true,
        latest_execution_decision_action: "live_candidate_recorded",
        latest_execution_runtime_mode: "live",
        telegram_alert_type: "OPERATOR_PLAN_SUMMARY",
        telegram_delivery_state: "sent",
      },
      t,
    );
    expect(lines.some((l) => l.includes("allow_trade"))).toBe(true);
    expect(lines.some((l) => l.toLowerCase().includes("playbook"))).toBe(
      true,
    );
    expect(lines.some((l) => l.includes("scale_out"))).toBe(true);
    expect(lines.some((l) => l.toLowerCase().includes("live-mirror"))).toBe(
      true,
    );
    expect(lines.some((l) => l.toLowerCase().includes("telegram"))).toBe(true);
  });

  it("summarizeTradeRationale empty when not allow_trade", () => {
    expect(
      summarizeTradeRationale({ trade_action: "do_not_trade" }, t),
    ).toEqual([]);
  });

  it("summarizeNoTradeReasons covers stop floor and live broker block branches", () => {
    const lines = summarizeNoTradeReasons(
      {
        trade_action: "abstain",
        market_family: "spot",
        instrument_supports_long_short: false,
        stop_distance_pct: 0.001,
        stop_min_executable_pct: 0.002,
        live_mirror_eligible: false,
        latest_execution_decision_action: "blocked",
        latest_execution_runtime_mode: "live",
      },
      t,
    );
    expect(lines.some((l) => l.toLowerCase().includes("distance"))).toBe(true);
    expect(lines.some((l) => l.toLowerCase().includes("spot"))).toBe(true);
    expect(
      lines.some((l) => l.toLowerCase().includes("live-mirror")),
    ).toBe(true);
    expect(lines.some((l) => l.toLowerCase().includes("live broker"))).toBe(
      true,
    );
  });

  it("summarizeNoTradeReasons covers ood, uncertainty and fragility branches", () => {
    const lines = summarizeNoTradeReasons(
      {
        trade_action: "no_trade",
        model_ood_alert: true,
        model_uncertainty_0_1: 0.7,
        stop_fragility_0_1: 0.9,
        stop_executability_0_1: 0.2,
      },
      t,
    );
    expect(lines.some((l) => l.toLowerCase().includes("ood"))).toBe(true);
    expect(
      lines.some(
        (l) =>
          l.toLowerCase().includes("uncertainty") ||
          l.toLowerCase().includes("modell") ||
          l.toLowerCase().includes("model"),
      ),
    ).toBe(true);
    expect(lines.some((l) => l.toLowerCase().includes("fragil"))).toBe(true);
  });

  it("summarizeNoTradeReasons falls back when no explicit reasons exist", () => {
    const lines = summarizeNoTradeReasons(
      { trade_action: "paper_only" },
      t,
    );
    expect(lines).toEqual([
      t("pages.signalsDetail.rationaleNo.fallbackNoBranch"),
    ]);
  });

  it("summarizeTradeRationale includes operator gate and governor clear branch", () => {
    const lines = summarizeTradeRationale(
      {
        trade_action: "allow_trade",
        decision_state: "accepted",
        router_operator_gate_required: true,
        allowed_leverage: 9,
        recommended_leverage: 7,
        stop_fragility_0_1: 0.22,
        stop_executability_0_1: 0.91,
        stop_distance_pct: 0.004,
        stop_budget_max_pct_allowed: 0.01,
        shadow_divergence_0_1: 0.02,
        live_execution_clear_for_real_money: true,
        instrument_product_type: "USDT-FUTURES",
        instrument_margin_account_mode: "crossed",
        operator_release_exists: true,
      },
      t,
    );
    expect(lines.some((l) => l.toLowerCase().includes("operator"))).toBe(true);
    expect(
      lines.some(
        (l) =>
          l.toLowerCase().includes("stop") &&
          l.toLowerCase().includes("fragil"),
      ),
    ).toBe(true);
    expect(
      lines.some(
        (l) =>
          l.toLowerCase().includes("governor") && l.toLowerCase().includes("no"),
      ),
    ).toBe(true);
  });

  it("summarizeTradeRationale includes live block reasons when present", () => {
    const lines = summarizeTradeRationale(
      {
        trade_action: "allow_trade",
        decision_state: "accepted",
        live_execution_block_reasons_json: [
          "portfolio_live_execution_policy",
        ],
      },
      t,
    );
    expect(
      lines.some(
        (l) => l.toLowerCase().includes("governor") && l.toLowerCase().includes("block"),
      ),
    ).toBe(true);
    expect(
      lines.some((l) => l.includes("portfolio_live_execution_policy")),
    ).toBe(true);
  });
});
