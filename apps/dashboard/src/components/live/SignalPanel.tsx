"use client";

import { useI18n } from "@/components/i18n/I18nProvider";
import type { LiveSignal } from "@/lib/types";

type Props = {
  signal: LiveSignal | null;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

const sk = (k: string) => `live.signalPanel.${k}` as const;

export function SignalPanel({ signal }: Props) {
  const { t } = useI18n();
  if (!signal) {
    return (
      <div className="panel">
        <h2>{t(sk("titleEmpty"))}</h2>
        <p className="muted degradation-inline">{t(sk("emptyBody"))}</p>
      </div>
    );
  }
  const warnings = Array.isArray(signal.risk_warnings_json)
    ? signal.risk_warnings_json
    : [];
  const regimeReasons = Array.isArray(signal.regime_reasons_json)
    ? signal.regime_reasons_json
    : [];
  const abstentionReasons = Array.isArray(signal.abstention_reasons_json)
    ? signal.abstention_reasons_json
    : [];
  const leverageReasons = Array.isArray(signal.leverage_cap_reasons_json)
    ? signal.leverage_cap_reasons_json
    : [];
  const instrumentMeta = asRecord(signal.instrument_metadata);
  return (
    <div className="panel">
      <h2>{t(sk("titleMain"))}</h2>
      <div className="signal-grid">
        <div>
          <span className="label">{t(sk("labelDirection"))}</span>
          <strong
            className={`dir ${
              signal.direction === "long"
                ? "dir-long"
                : signal.direction === "short"
                  ? "dir-short"
                  : "dir-neutral"
            }`}
          >
            {signal.direction}
          </strong>
        </div>
        <div>
          <span className="label">{t(sk("labelLane"))}</span>
          <strong>{signal.meta_trade_lane ?? "—"}</strong>
        </div>
        <div>
          <span className="label">{t(sk("labelPlaybook"))}</span>
          <strong>{signal.playbook_id ?? "—"}</strong>
        </div>
        <div>
          <span className="label">{t(sk("labelPlaybookFamily"))}</span>
          <strong>{signal.playbook_family ?? "—"}</strong>
        </div>
        <div>
          <span className="label">{t(sk("labelPlaybookMode"))}</span>
          <strong>{signal.playbook_decision_mode ?? "—"}</strong>
        </div>
        <div>
          <span className="label">{t(sk("labelStrength"))}</span>
          <strong>{signal.signal_strength_0_100}</strong>
        </div>
        <div>
          <span className="label">{t(sk("labelProbability"))}</span>
          <strong>{(signal.probability_0_1 * 100).toFixed(1)}%</strong>
        </div>
        <div>
          <span className="label">{t(sk("labelTakeTrade"))}</span>
          <strong>
            {typeof signal.take_trade_prob === "number"
              ? `${(signal.take_trade_prob * 100).toFixed(1)}%`
              : "—"}
          </strong>
        </div>
        <div>
          <span className="label">{t(sk("labelExpReturn"))}</span>
          <strong>
            {typeof signal.expected_return_bps === "number"
              ? `${signal.expected_return_bps.toFixed(1)} bps`
              : "—"}
          </strong>
        </div>
        <div>
          <span className="label">{t(sk("labelExpMae"))}</span>
          <strong>
            {typeof signal.expected_mae_bps === "number"
              ? `${signal.expected_mae_bps.toFixed(1)} bps`
              : "—"}
          </strong>
        </div>
        <div>
          <span className="label">{t(sk("labelExpMfe"))}</span>
          <strong>
            {typeof signal.expected_mfe_bps === "number"
              ? `${signal.expected_mfe_bps.toFixed(1)} bps`
              : "—"}
          </strong>
        </div>
        <div>
          <span className="label">{t(sk("labelUncertainty"))}</span>
          <strong>
            {typeof signal.model_uncertainty_0_1 === "number"
              ? `${(signal.model_uncertainty_0_1 * 100).toFixed(1)}%`
              : "—"}
          </strong>
          {typeof signal.uncertainty_effective_for_leverage_0_1 === "number" ? (
            <div className="text-xs text-muted-foreground">
              {t(sk("labelUncLeverageHint"))}{" "}
              {(signal.uncertainty_effective_for_leverage_0_1 * 100).toFixed(1)}
              %
            </div>
          ) : null}
        </div>
        <div>
          <span className="label">{t(sk("labelPolicyConfidence"))}</span>
          <strong>
            {typeof signal.decision_confidence_0_1 === "number"
              ? `${(signal.decision_confidence_0_1 * 100).toFixed(1)}%`
              : "—"}
          </strong>
        </div>
        <div>
          <span className="label">{t(sk("labelShadowDiv"))}</span>
          <strong>
            {typeof signal.shadow_divergence_0_1 === "number"
              ? `${(signal.shadow_divergence_0_1 * 100).toFixed(1)}%`
              : "—"}
          </strong>
        </div>
        <div>
          <span className="label">{t(sk("labelTradeAction"))}</span>
          <strong>{signal.trade_action ?? "—"}</strong>
        </div>
        <div>
          <span className="label">{t(sk("labelLevFree"))}</span>
          <strong>
            {typeof signal.allowed_leverage === "number"
              ? `${signal.allowed_leverage}x`
              : "—"}
          </strong>
        </div>
        <div>
          <span className="label">{t(sk("labelLevFinal"))}</span>
          <strong>
            {typeof signal.recommended_leverage === "number"
              ? `${signal.recommended_leverage}x`
              : "—"}
          </strong>
        </div>
        <div>
          <span className="label">{t(sk("labelOod"))}</span>
          <strong>
            {signal.model_ood_alert ? t(sk("oodAlert")) : t(sk("oodOk"))}
          </strong>
        </div>
        <div>
          <span className="label">{t(sk("labelClass"))}</span>
          <strong>{signal.signal_class}</strong>
        </div>
        <div>
          <span className="label">{t(sk("labelRegime"))}</span>
          <strong>{signal.market_regime ?? "—"}</strong>
        </div>
        <div>
          <span className="label">{t(sk("labelRegimeState"))}</span>
          <strong>{signal.regime_state ?? "—"}</strong>
        </div>
        <div>
          <span className="label">{t(sk("labelRegimeTransition"))}</span>
          <strong>{signal.regime_transition_state ?? "—"}</strong>
        </div>
        <div>
          <span className="label">{t(sk("labelBias"))}</span>
          <strong>{signal.regime_bias ?? "—"}</strong>
        </div>
        <div>
          <span className="label">{t(sk("labelRegimeConf"))}</span>
          <strong>
            {typeof signal.regime_confidence_0_1 === "number"
              ? `${(signal.regime_confidence_0_1 * 100).toFixed(1)}%`
              : "—"}
          </strong>
        </div>
        <div>
          <span className="label">{t(sk("labelMetaModel"))}</span>
          <strong>{signal.take_trade_model_version ?? "—"}</strong>
        </div>
        <div>
          <span className="label">{t(sk("labelStrategy"))}</span>
          <strong>{signal.strategy_name ?? "—"}</strong>
        </div>
        <div>
          <span className="label">{t(sk("labelCanon"))}</span>
          <strong>{signal.canonical_instrument_id ?? "—"}</strong>
        </div>
        <div>
          <span className="label">{t(sk("labelFamily"))}</span>
          <strong>{signal.market_family ?? "—"}</strong>
        </div>
        <div>
          <span className="label">{t(sk("labelStopBudget"))}</span>
          <strong>
            {typeof signal.stop_distance_pct === "number"
              ? `${(signal.stop_distance_pct * 100).toFixed(2)}%`
              : "—"}{" "}
            /{" "}
            {typeof signal.stop_budget_max_pct_allowed === "number"
              ? `${(signal.stop_budget_max_pct_allowed * 100).toFixed(2)}%`
              : "—"}
          </strong>
        </div>
        <div>
          <span className="label">{t(sk("labelStopFragExec"))}</span>
          <strong>
            {typeof signal.stop_fragility_0_1 === "number"
              ? signal.stop_fragility_0_1.toFixed(2)
              : "—"}{" "}
            /{" "}
            {typeof signal.stop_executability_0_1 === "number"
              ? signal.stop_executability_0_1.toFixed(2)
              : "—"}
          </strong>
        </div>
      </div>
      {instrumentMeta ? (
        <section className="mt">
          <h3>{t(sk("instrumentMetaTitle"))}</h3>
          <ul className="news-list">
            <li>
              {t(sk("metaSource"))}:{" "}
              {String(instrumentMeta.metadata_source ?? "—")} ·{" "}
              {t(sk("metaVerified"))}:{" "}
              {String(instrumentMeta.metadata_verified ?? "—")}
            </li>
            <li>
              {t(sk("metaProduct"))}:{" "}
              {String(instrumentMeta.product_type ?? "—")} ·{" "}
              {t(sk("metaMarginMode"))}:{" "}
              {String(instrumentMeta.margin_account_mode ?? "—")}
            </li>
            <li>
              {t(sk("metaSupportsLev"))}:{" "}
              {String(instrumentMeta.supports_leverage ?? "—")} ·{" "}
              {t(sk("metaLongShort"))}:{" "}
              {String(instrumentMeta.supports_long_short ?? "—")} ·{" "}
              {t(sk("metaReduceOnly"))}:{" "}
              {String(instrumentMeta.supports_reduce_only ?? "—")}
            </li>
          </ul>
        </section>
      ) : null}
      {regimeReasons.length > 0 ? (
        <section className="mt">
          <h3>{t(sk("regimeFacts"))}</h3>
          <ul className="warnings">
            {regimeReasons.map((reason, i) => (
              <li key={i}>
                {typeof reason === "string" ? reason : JSON.stringify(reason)}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {signal.explain_short ? (
        <section className="mt">
          <h3>{t(sk("rationale"))}</h3>
          <p className="explain">{signal.explain_short}</p>
        </section>
      ) : null}
      {warnings.length > 0 ? (
        <section className="mt">
          <h3>{t(sk("riskHints"))}</h3>
          <ul className="warnings">
            {warnings.map((w, i) => (
              <li key={i}>{typeof w === "string" ? w : JSON.stringify(w)}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {abstentionReasons.length > 0 ? (
        <section className="mt">
          <h3>{t(sk("abstention"))}</h3>
          <ul className="warnings">
            {abstentionReasons.map((reason, i) => (
              <li key={i}>
                {typeof reason === "string" ? reason : JSON.stringify(reason)}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {leverageReasons.length > 0 ? (
        <section className="mt">
          <h3>{t(sk("leverageCaps"))}</h3>
          <ul className="warnings">
            {leverageReasons.map((reason, i) => (
              <li key={i}>
                {typeof reason === "string" ? reason : JSON.stringify(reason)}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
