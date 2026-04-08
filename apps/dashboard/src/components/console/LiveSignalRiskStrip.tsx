import { formatNum, formatPct01 } from "@/lib/format";
import type { LiveSignal } from "@/lib/types";

type Translate = (
  key: string,
  vars?: Record<string, string | number | boolean>,
) => string;

/**
 * Risiko-Kennzahlen zum aktuellen Live-Signal — gemeinsam fuer Cockpit und aehnliche Ops-Ansichten.
 */
export function LiveSignalRiskStrip({
  signal,
  t,
}: Readonly<{
  signal: LiveSignal | null;
  t: Translate;
}>) {
  if (!signal) {
    return (
      <p className="muted degradation-inline">
        {t("pages.ops.riskStripNoSignal")}
      </p>
    );
  }
  const caps = Array.isArray(signal.leverage_cap_reasons_json)
    ? signal.leverage_cap_reasons_json
    : [];
  return (
    <ul className="news-list operator-metric-list">
      <li>
        {t("pages.ops.riskStripConfidence")}:{" "}
        <strong>{formatPct01(signal.decision_confidence_0_1)}</strong>
      </li>
      <li>
        {t("pages.ops.riskStripModelUncertainty")}:{" "}
        <strong>{formatPct01(signal.model_uncertainty_0_1)}</strong>
      </li>
      <li>
        {t("pages.ops.riskStripLeverageUncertainty")}:{" "}
        <strong>
          {formatPct01(signal.uncertainty_effective_for_leverage_0_1)}
        </strong>
      </li>
      <li>
        {t("pages.ops.riskStripExpectedEdge")}:{" "}
        <strong>
          {typeof signal.expected_return_bps === "number"
            ? `${formatNum(signal.expected_return_bps, 2)} bps`
            : "—"}
        </strong>
      </li>
      <li>
        {t("pages.ops.riskStripShadowDiv")}:{" "}
        <strong>{formatPct01(signal.shadow_divergence_0_1)}</strong>
      </li>
      <li>
        {t("pages.ops.riskStripRecLev")}:{" "}
        <strong>
          {typeof signal.recommended_leverage === "number"
            ? `${signal.recommended_leverage}x`
            : "—"}
        </strong>{" "}
        ({t("pages.ops.riskStripLevFree")}:{" "}
        <strong>
          {typeof signal.allowed_leverage === "number"
            ? `${signal.allowed_leverage}x`
            : "—"}
        </strong>
        )
      </li>
      <li>
        {t("pages.ops.riskStripTakeTrade")}:{" "}
        <strong>
          {signal.take_trade_model_version ??
            signal.take_trade_model_run_id ??
            "—"}
        </strong>
      </li>
      <li>
        {t("pages.ops.riskStripTradeAction")}:{" "}
        <strong>{signal.trade_action ?? "—"}</strong>
      </li>
      {caps.length > 0 ? (
        <li className="operator-warn">
          {t("pages.ops.riskStripLevCaps")}: <code>{JSON.stringify(caps)}</code>
        </li>
      ) : null}
    </ul>
  );
}
