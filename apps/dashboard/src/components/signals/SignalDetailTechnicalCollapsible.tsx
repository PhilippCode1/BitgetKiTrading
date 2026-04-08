import type { ReactNode } from "react";

import {
  formatDistancePctField,
  formatNum,
  formatPct01,
  formatTsMs,
} from "@/lib/format";
import type { SignalDetail } from "@/lib/types";

type Translate = (
  key: string,
  vars?: Record<string, string | number>,
) => string;

type Props = Readonly<{
  detail: SignalDetail;
  /** Vollständiges reasons_json (Explain-API bevorzugt, sonst Signalzeile). */
  reasonsJsonForAudit: unknown;
  t: Translate;
}>;

function yn(t: Translate, v: boolean | null | undefined): string {
  if (v === true) return t("pages.signalsDetail.boolYes");
  if (v === false) return t("pages.signalsDetail.boolNo");
  return "—";
}

function TechRow({
  label,
  children,
}: Readonly<{ label: string; children: ReactNode }>) {
  return (
    <div>
      <span className="label mono-small">{label}</span>
      <div>{children}</div>
    </div>
  );
}

/**
 * Aufklappbarer Operatoren-Bereich: Kennzahlen-Grid, Persistenz, Stops, Execution, JSON-Audit.
 */
export function SignalDetailTechnicalCollapsible({
  detail,
  reasonsJsonForAudit,
  t,
}: Props) {
  const tm = (key: string) => t(`pages.signalsDetail.techMetrics.${key}`);
  const tf = (key: string) => t(`pages.signalsDetail.techFields.${key}`);

  const oodDisplay = detail.model_ood_alert
    ? t("pages.signalsDetail.techOodValueAlert", {
        score: formatPct01(detail.model_ood_score_0_1 ?? null),
      })
    : t("pages.signalsDetail.techOodValueOk");

  const routerGate =
    detail.router_operator_gate_required === true
      ? t("pages.signalsDetail.techRouterGateYes")
      : detail.router_operator_gate_required === false
        ? t("pages.signalsDetail.techRouterGateNo")
        : "—";

  const operatorRelease =
    detail.operator_release_exists === true
      ? t("pages.signalsDetail.techOperatorReleaseYes", {
          source: detail.operator_release_source ?? "unknown",
        })
      : detail.operator_release_exists === false
        ? t("pages.signalsDetail.boolNo")
        : "—";

  const liveMoney =
    detail.live_execution_clear_for_real_money === false
      ? t("pages.signalsDetail.techLiveMoneyClearNo")
      : detail.live_execution_clear_for_real_money === true
        ? t("pages.signalsDetail.techLiveMoneyClearYes")
        : "—";

  return (
    <details className="panel signal-detail-technical-collapsible">
      <summary className="signal-detail-technical-collapsible__summary">
        <span className="signal-detail-technical-collapsible__summary-title">
          {t("pages.signalsDetail.techToggle")}
        </span>
      </summary>
      <div className="signal-detail-technical-nest">
        <p className="muted small">{t("pages.signalsDetail.techToggleLead")}</p>

        <h3 className="h3-quiet signal-detail-technical-nest__h">
          {t("pages.signalsDetail.techGroupMetrics")}
        </h3>
        <div className="signal-grid">
          <TechRow label={tm("direction")}>
            <div>{detail.direction}</div>
          </TechRow>
          <TechRow label={tm("strength")}>
            <div>{formatNum(detail.signal_strength_0_100, 1)}</div>
          </TechRow>
          <TechRow label={tm("probability")}>
            <div>{formatPct01(detail.probability_0_1)}</div>
          </TechRow>
          <TechRow label={tm("takeTradeProb")}>
            <div>{formatPct01(detail.take_trade_prob ?? null)}</div>
          </TechRow>
          <TechRow label={tm("expReturn")}>
            <div>
              {detail.expected_return_bps == null
                ? "—"
                : `${formatNum(detail.expected_return_bps, 1)} bps`}
            </div>
          </TechRow>
          <TechRow label={tm("expMae")}>
            <div>
              {detail.expected_mae_bps == null
                ? "—"
                : `${formatNum(detail.expected_mae_bps, 1)} bps`}
            </div>
          </TechRow>
          <TechRow label={tm("expMfe")}>
            <div>
              {detail.expected_mfe_bps == null
                ? "—"
                : `${formatNum(detail.expected_mfe_bps, 1)} bps`}
            </div>
          </TechRow>
          <TechRow label={tm("uncertainty")}>
            <div>{formatPct01(detail.model_uncertainty_0_1 ?? null)}</div>
          </TechRow>
          <TechRow label={tm("uncertaintyLeverage")}>
            <div>
              {formatPct01(
                detail.uncertainty_effective_for_leverage_0_1 ?? null,
              )}
            </div>
          </TechRow>
          <TechRow label={tm("shadowDiv")}>
            <div>{formatPct01(detail.shadow_divergence_0_1 ?? null)}</div>
          </TechRow>
          <TechRow label={tm("ood")}>
            <div>{oodDisplay}</div>
          </TechRow>
          <TechRow label={tm("tradeAction")}>
            <div>{detail.trade_action ?? "—"}</div>
          </TechRow>
          <TechRow label={tm("metaDecision")}>
            <div>{detail.meta_decision_action ?? "—"}</div>
            <div className="muted small mono-small">
              {tf("metaDecisionKernelVersion")}:{" "}
              {detail.meta_decision_kernel_version ?? "—"}
            </div>
          </TechRow>
          <TechRow label={tm("lane")}>
            <div>{detail.meta_trade_lane ?? "—"}</div>
          </TechRow>
          <TechRow label={tm("levAllowed")}>
            <div>
              {detail.allowed_leverage == null
                ? "—"
                : `${formatNum(detail.allowed_leverage, 0)}×`}
            </div>
          </TechRow>
          <TechRow label={tm("levFinal")}>
            <div>
              {detail.recommended_leverage == null
                ? "—"
                : `${formatNum(detail.recommended_leverage, 0)}×`}
            </div>
          </TechRow>
          <TechRow label={tm("signalClass")}>
            <div>{detail.signal_class}</div>
          </TechRow>
          <TechRow label={tm("regime")}>
            <div>{detail.market_regime ?? "—"}</div>
          </TechRow>
          <TechRow label={tm("regimeBias")}>
            <div>{detail.regime_bias ?? "—"}</div>
          </TechRow>
          <TechRow label={tm("metaModel")}>
            <div>{detail.take_trade_model_version ?? "—"}</div>
          </TechRow>
          <TechRow label={tm("timeframe")}>
            <div>{detail.timeframe}</div>
          </TechRow>
          <TechRow label={tm("analysisTs")}>
            <div>{formatTsMs(detail.analysis_ts_ms)}</div>
          </TechRow>
        </div>

        <h3 className="h3-quiet signal-detail-technical-nest__h">
          {t("pages.signalsDetail.techGroupInstrument")}
        </h3>
        <div className="signal-grid">
          <TechRow label={tf("canonicalInstrument")}>
            <div className="mono-small">
              {detail.canonical_instrument_id ?? "—"}
            </div>
          </TechRow>
          <TechRow label={tf("instrumentVenue")}>
            <div>{detail.instrument_venue ?? "—"}</div>
          </TechRow>
          <TechRow label={tf("marketFamily")}>
            <div>{detail.market_family ?? "—"}</div>
          </TechRow>
          <TechRow label={tf("instrumentProductType")}>
            <div>{detail.instrument_product_type ?? "—"}</div>
          </TechRow>
          <TechRow label={tf("instrumentMarginMode")}>
            <div>{detail.instrument_margin_account_mode ?? "—"}</div>
          </TechRow>
          <TechRow label={tf("metadataSource")}>
            <div className="mono-small">
              {detail.instrument_metadata_source ?? "—"}
            </div>
          </TechRow>
          <TechRow label={tf("metadataSnapshotId")}>
            <div className="mono-small">
              {detail.instrument_metadata_snapshot_id ?? "—"}
            </div>
          </TechRow>
          <TechRow label={tf("instrumentCategoryKey")}>
            <div className="mono-small">
              {detail.instrument_category_key ?? "—"}
            </div>
          </TechRow>
          <TechRow label={tf("metadataVerified")}>
            <div>{yn(t, detail.instrument_metadata_verified)}</div>
          </TechRow>
          <TechRow label={tf("baseQuoteSettle")}>
            <div>
              {detail.instrument_base_coin ?? "—"} /{" "}
              {detail.instrument_quote_coin ?? "—"} /{" "}
              {detail.instrument_settle_coin ?? "—"}
            </div>
          </TechRow>
          <TechRow label={tf("inventoryAnalytics")}>
            <div>
              {yn(t, detail.instrument_inventory_visible)} /{" "}
              {yn(t, detail.instrument_analytics_eligible)}
            </div>
          </TechRow>
          <TechRow label={tf("eligibilityFlags")}>
            <div>
              {yn(t, detail.instrument_paper_shadow_eligible)} /{" "}
              {yn(t, detail.instrument_live_execution_enabled)} /{" "}
              {yn(t, detail.instrument_execution_disabled)}
            </div>
          </TechRow>
          <TechRow label={tf("leverageReduceOnly")}>
            <div>
              {yn(t, detail.instrument_supports_leverage)} /{" "}
              {yn(t, detail.instrument_supports_reduce_only)}
            </div>
          </TechRow>
          <TechRow label={tf("fundingOpenInterest")}>
            <div>
              {yn(t, detail.instrument_supports_funding)} /{" "}
              {yn(t, detail.instrument_supports_open_interest)}
            </div>
          </TechRow>
          <TechRow label={tf("longShort")}>
            <div>{yn(t, detail.instrument_supports_long_short)}</div>
          </TechRow>
          <TechRow label={tf("shorting")}>
            <div>{yn(t, detail.instrument_supports_shorting)}</div>
          </TechRow>
          <TechRow label={tf("strategyName")}>
            <div>{detail.strategy_name ?? "—"}</div>
          </TechRow>
          <TechRow label={tf("playbookId")}>
            <div>{detail.playbook_id ?? "—"}</div>
          </TechRow>
          <TechRow label={tf("playbookFamily")}>
            <div>{detail.playbook_family ?? "—"}</div>
          </TechRow>
          <TechRow label={tf("playbookDecisionMode")}>
            <div>{detail.playbook_decision_mode ?? "—"}</div>
          </TechRow>
          <TechRow label={tf("regimeState")}>
            <div>{detail.regime_state ?? "—"}</div>
          </TechRow>
          <TechRow label={tf("regimeSubstate")}>
            <div>{detail.regime_substate ?? "—"}</div>
          </TechRow>
          <TechRow label={tf("regimeTransition")}>
            <div>{detail.regime_transition_state ?? "—"}</div>
          </TechRow>
          <TechRow label={tf("specialistRouterId")}>
            <div className="mono-small">
              {detail.specialist_router_id ?? "—"}
            </div>
          </TechRow>
          <TechRow label={tf("routerSelectedPlaybookId")}>
            <div>{detail.router_selected_playbook_id ?? "—"}</div>
          </TechRow>
          <TechRow label={tf("routerOperatorGate")}>
            <div>{routerGate}</div>
          </TechRow>
          <TechRow label={tf("exitFamilyEnsemble")}>
            <div>
              {detail.exit_family_effective_primary ?? "—"} /{" "}
              {detail.exit_family_primary_ensemble ?? "—"}
            </div>
          </TechRow>
        </div>

        <h3 className="h3-quiet signal-detail-technical-nest__h">
          {t("pages.signalsDetail.techGroupStop")}
        </h3>
        <p className="muted small">
          {t("pages.signalsDetail.techGroupStopLead")}
        </p>
        <p className="muted small">
          {t("pages.signalsDetail.techStopAuditHint")}
        </p>
        <div className="signal-grid">
          <TechRow label={tf("stopDistance")}>
            <div>
              {formatDistancePctField(detail.stop_distance_pct ?? null)}
            </div>
          </TechRow>
          <TechRow label={tf("stopBudgetMax")}>
            <div>
              {formatDistancePctField(
                detail.stop_budget_max_pct_allowed ?? null,
              )}
            </div>
          </TechRow>
          <TechRow label={tf("stopMinExecutable")}>
            <div>
              {formatDistancePctField(detail.stop_min_executable_pct ?? null)}
            </div>
          </TechRow>
          <TechRow label={tf("stopFragility")}>
            <div>
              {detail.stop_fragility_0_1 != null
                ? formatNum(detail.stop_fragility_0_1, 3)
                : "—"}
            </div>
          </TechRow>
          <TechRow label={tf("stopExecutability")}>
            <div>
              {detail.stop_executability_0_1 != null
                ? formatNum(detail.stop_executability_0_1, 3)
                : "—"}
            </div>
          </TechRow>
          <TechRow label={tf("stopQuality")}>
            <div>
              {detail.stop_quality_0_1 != null
                ? formatNum(detail.stop_quality_0_1, 3)
                : "—"}
            </div>
          </TechRow>
          <TechRow label={tf("stopToSpreadRatio")}>
            <div>
              {detail.stop_to_spread_ratio != null
                ? formatNum(detail.stop_to_spread_ratio, 3)
                : "—"}
            </div>
          </TechRow>
          <TechRow label={tf("stopBudgetPolicyVersion")}>
            <div className="mono-small">
              {detail.stop_budget_policy_version ?? "—"}
            </div>
          </TechRow>
        </div>

        <h3 className="h3-quiet signal-detail-technical-nest__h">
          {t("pages.signalsDetail.techGroupExec")}
        </h3>
        <p className="muted small">
          {t("pages.signalsDetail.techGroupExecLead")}
        </p>
        <div className="signal-grid">
          <TechRow label={tf("latestExecutionId")}>
            <div className="mono-small">
              {detail.latest_execution_id ?? "—"}
            </div>
          </TechRow>
          <TechRow label={tf("latestDecisionAction")}>
            <div>{detail.latest_execution_decision_action ?? "—"}</div>
          </TechRow>
          <TechRow label={tf("latestDecisionReason")}>
            <div>{detail.latest_execution_decision_reason ?? "—"}</div>
          </TechRow>
          <TechRow label={tf("execRequestedRuntime")}>
            <div>
              {detail.latest_execution_requested_mode ?? "—"} /{" "}
              {detail.latest_execution_runtime_mode ?? "—"}
            </div>
          </TechRow>
          <TechRow label={tf("operatorReleaseExists")}>
            <div>{operatorRelease}</div>
          </TechRow>
          <TechRow label={tf("operatorReleaseTs")}>
            <div>{detail.operator_release_ts ?? "—"}</div>
          </TechRow>
          <TechRow label={tf("liveMirrorEligible")}>
            <div>
              {detail.live_mirror_eligible == null
                ? "—"
                : String(detail.live_mirror_eligible)}
            </div>
          </TechRow>
          <TechRow label={tf("shadowLiveMatchOk")}>
            <div>
              {detail.shadow_live_match_ok == null
                ? "—"
                : String(detail.shadow_live_match_ok)}
            </div>
          </TechRow>
          <TechRow label={tf("telegramAlertType")}>
            <div>{detail.telegram_alert_type ?? "—"}</div>
          </TechRow>
          <TechRow label={tf("telegramDeliveryState")}>
            <div>{detail.telegram_delivery_state ?? "—"}</div>
          </TechRow>
          <TechRow label={tf("telegramMessageId")}>
            <div>{detail.telegram_message_id ?? "—"}</div>
          </TechRow>
          <TechRow label={tf("telegramSentTs")}>
            <div>{detail.telegram_sent_ts ?? "—"}</div>
          </TechRow>
        </div>

        {Array.isArray(detail.target_projection_models_json) &&
        detail.target_projection_models_json.length > 0 ? (
          <details className="panel reasons signal-detail-technical-nest__sub">
            <summary>{t("pages.signalsDetail.techJsonProjection")}</summary>
            <pre className="json-mini">
              {JSON.stringify(detail.target_projection_models_json, null, 2)}
            </pre>
          </details>
        ) : null}
        {Array.isArray(detail.abstention_reasons_json) &&
        detail.abstention_reasons_json.length > 0 ? (
          <details className="panel reasons signal-detail-technical-nest__sub">
            <summary>{t("pages.signalsDetail.techJsonAbstention")}</summary>
            <pre className="json-mini">
              {JSON.stringify(detail.abstention_reasons_json, null, 2)}
            </pre>
          </details>
        ) : null}
        {Array.isArray(detail.leverage_cap_reasons_json) &&
        detail.leverage_cap_reasons_json.length > 0 ? (
          <details className="panel reasons signal-detail-technical-nest__sub">
            <summary>{t("pages.signalsDetail.techJsonLeverageCaps")}</summary>
            <pre className="json-mini">
              {JSON.stringify(detail.leverage_cap_reasons_json, null, 2)}
            </pre>
          </details>
        ) : null}

        <h3 className="h3-quiet signal-detail-technical-nest__h">
          {t("pages.signalsDetail.techGroupPolicy")}
        </h3>
        <p className="muted small">
          {t("pages.signalsDetail.techGroupPolicyLead")}
        </p>
        <p className="muted small">{t("pages.signalsDetail.techPolicyBody")}</p>
        <div className="signal-grid">
          <TechRow label={tf("liveMoneyPolicy")}>
            <div>{liveMoney}</div>
          </TechRow>
        </div>
        {Array.isArray(detail.governor_universal_hard_block_reasons_json) &&
        detail.governor_universal_hard_block_reasons_json.length > 0 ? (
          <details className="panel reasons signal-detail-technical-nest__sub">
            <summary>{t("pages.signalsDetail.techJsonGovUniversal")}</summary>
            <pre className="json-mini">
              {JSON.stringify(
                detail.governor_universal_hard_block_reasons_json,
                null,
                2,
              )}
            </pre>
          </details>
        ) : null}
        {Array.isArray(detail.live_execution_block_reasons_json) &&
        detail.live_execution_block_reasons_json.length > 0 ? (
          <details className="panel reasons signal-detail-technical-nest__sub">
            <summary>{t("pages.signalsDetail.techJsonGovLive")}</summary>
            <pre className="json-mini">
              {JSON.stringify(
                detail.live_execution_block_reasons_json,
                null,
                2,
              )}
            </pre>
          </details>
        ) : null}
        {detail.portfolio_risk_synthesis_json &&
        Object.keys(detail.portfolio_risk_synthesis_json).length > 0 ? (
          <details className="panel reasons signal-detail-technical-nest__sub">
            <summary>{t("pages.signalsDetail.techJsonPortfolio")}</summary>
            <pre className="json-mini">
              {JSON.stringify(detail.portfolio_risk_synthesis_json, null, 2)}
            </pre>
          </details>
        ) : null}

        {detail.instrument_metadata &&
        Object.keys(detail.instrument_metadata).length > 0 ? (
          <details className="panel reasons signal-detail-technical-nest__sub">
            <summary>{t("pages.signalsDetail.techJsonInstrumentMeta")}</summary>
            <pre className="json-mini">
              {JSON.stringify(detail.instrument_metadata, null, 2)}
            </pre>
          </details>
        ) : null}
        {detail.shadow_live_hard_violations ? (
          <details className="panel reasons signal-detail-technical-nest__sub">
            <summary>{t("pages.signalsDetail.techJsonShadowHard")}</summary>
            <pre className="json-mini">
              {JSON.stringify(detail.shadow_live_hard_violations, null, 2)}
            </pre>
          </details>
        ) : null}
        {detail.shadow_live_soft_violations ? (
          <details className="panel reasons signal-detail-technical-nest__sub">
            <summary>{t("pages.signalsDetail.techJsonShadowSoft")}</summary>
            <pre className="json-mini">
              {JSON.stringify(detail.shadow_live_soft_violations, null, 2)}
            </pre>
          </details>
        ) : null}

        <details className="panel reasons signal-detail-technical-nest__sub signal-detail-technical-nest__sub--primary">
          <summary>{t("pages.signalsDetail.techFullReasonsJson")}</summary>
          <pre className="json-mini">
            {JSON.stringify(reasonsJsonForAudit ?? null, null, 2)}
          </pre>
        </details>
      </div>
    </details>
  );
}
