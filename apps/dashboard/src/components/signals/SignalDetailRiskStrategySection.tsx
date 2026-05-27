import { RiskWarningsPanel } from "@/components/panels/RiskWarningsPanel";
import { ContentPanel } from "@/components/ui/ContentPanel";
import { formatDistancePctField, formatNum, formatPct01 } from "@/lib/format";
import {
  blockReasonTokens,
  renderDecisionToken,
  signalAssetTierToken,
  signalDataQualityToken,
  signalLiquidityToken,
  signalLiveReleaseToken,
  signalRiskStatusToken,
  tradeActionToken,
  type TranslateLike,
} from "@/lib/signal-decision-tokens";
import {
  summarizeNoTradeReasons,
  summarizeTradeRationale,
} from "@/lib/signal-rationale";
import type { SignalDetail, SignalExplainResponse } from "@/lib/types";

type Translate = (
  key: string,
  vars?: Record<string, string | number | boolean>,
) => string;

type Props = Readonly<{
  detail: SignalDetail;
  explain: SignalExplainResponse | null;
  t: Translate;
}>;

const DC_SCOPE = "pages.signalsDetail.decisionCenter" as const;

/**
 * Schicht: Risiko & Strategie — Warnungen, kompakte Zahlen in Worten, No-Trade / Trade-Begründung.
 */
export function SignalDetailRiskStrategySection({ detail, explain, t }: Props) {
  const snap: string[] = [];
  if (detail.allowed_leverage != null || detail.recommended_leverage != null) {
    snap.push(
      t("pages.signalsDetail.riskSnapshotLeverage", {
        allowed:
          detail.allowed_leverage == null
            ? "—"
            : `${formatNum(detail.allowed_leverage, 0)}`,
        recommended:
          detail.recommended_leverage == null
            ? "—"
            : `${formatNum(detail.recommended_leverage, 0)}`,
      }),
    );
  }
  if (detail.stop_distance_pct != null) {
    snap.push(
      t("pages.signalsDetail.riskSnapshotStop", {
        dist: formatDistancePctField(detail.stop_distance_pct),
      }),
    );
  }
  if (
    typeof detail.model_uncertainty_0_1 === "number" &&
    detail.model_uncertainty_0_1 >= 0.45
  ) {
    snap.push(
      t("pages.signalsDetail.riskSnapshotUncertainty", {
        pct: formatPct01(detail.model_uncertainty_0_1),
      }),
    );
  }
  if (detail.model_ood_alert) {
    snap.push(t("pages.signalsDetail.riskSnapshotOod"));
  }

  return (
    <ContentPanel className="signal-detail-risk-strategy">
      <h2 className="h3-quiet">{t("pages.signalsDetail.sectionRiskTitle")}</h2>
      <p className="muted small">{t("pages.signalsDetail.sectionRiskLead")}</p>
      {snap.length > 0 ? (
        <ul className="signal-detail-risk-snapshot muted small">
          {snap.map((line) => (
            <li key={line.slice(0, 48)}>{line}</li>
          ))}
        </ul>
      ) : null}
      {explain ? (
        <div className="signal-detail-risk-warnings">
          <RiskWarningsPanel warnings={explain.risk_warnings_json} t={t} />
        </div>
      ) : null}
      <div className="panel signal-explain-layer signal-detail-gov-asset-context">
        <h3 className="h3-quiet">
          {t("pages.signalsDetail.govAssetContextTitle")}
        </h3>
        <p className="muted small">
          {t("pages.signalsDetail.govAssetContextLead")}
        </p>
        <ul className="news-list">
          <li>
            {t("pages.signalsDetail.tradeActionLabel")}:{" "}
            {renderDecisionToken(
              t as TranslateLike,
              DC_SCOPE,
              tradeActionToken(detail.trade_action),
            )}
          </li>
          <li>
            {t("pages.signalsDetail.riskStatusLabel")}:{" "}
            {renderDecisionToken(
              t as TranslateLike,
              DC_SCOPE,
              signalRiskStatusToken(detail),
            )}
          </li>
          <li>
            {t("pages.signalsDetail.assetTierLabel")}:{" "}
            {renderDecisionToken(
              t as TranslateLike,
              DC_SCOPE,
              signalAssetTierToken(detail),
            )}
          </li>
          <li>
            {t("pages.signalsDetail.dataQualityLabel")}:{" "}
            {renderDecisionToken(
              t as TranslateLike,
              DC_SCOPE,
              signalDataQualityToken(detail),
            )}
          </li>
          <li>
            {t("pages.signalsDetail.liquidityLabel")}:{" "}
            {renderDecisionToken(
              t as TranslateLike,
              DC_SCOPE,
              signalLiquidityToken(detail),
            )}
          </li>
          <li>
            {t("pages.signalsDetail.liveReleaseLabel")}:{" "}
            {renderDecisionToken(
              t as TranslateLike,
              DC_SCOPE,
              signalLiveReleaseToken(detail),
            )}
          </li>
        </ul>
        <p className="muted small signal-detail-gov-asset-context__blocks">
          {t("pages.signalsDetail.blockReasonsLabel")}:{" "}
          {blockReasonTokens(detail.live_execution_block_reasons_json, 4)
            .map((token) => renderDecisionToken(t as TranslateLike, DC_SCOPE, token))
            .join(" · ")}
        </p>
      </div>
      <div className="grid-2 signal-detail-rationale-grid">
        <div className="panel signal-explain-layer">
          <div className="signal-explain-layer__head">
            <h3 className="h3-quiet">
              {t("pages.signalsDetail.rationaleNoTradeTitle")}
            </h3>
            <span className="status-pill">
              {t("pages.signalsDetail.badgeDetailMirror")}
            </span>
          </div>
          <p className="muted small">
            {t("pages.signalsDetail.rationaleNoTradeLead")}
          </p>
          <ul className="news-list">
            {summarizeNoTradeReasons(detail, t).map((line, i) => (
              <li key={`nt-${i}-${line.slice(0, 40)}`}>{line}</li>
            ))}
          </ul>
        </div>
        <div className="panel signal-explain-layer">
          <div className="signal-explain-layer__head">
            <h3 className="h3-quiet">
              {t("pages.signalsDetail.rationaleTradeTitle")}
            </h3>
            <span className="status-pill">
              {t("pages.signalsDetail.badgeDetailMirror")}
            </span>
          </div>
          <p className="muted small">
            {t("pages.signalsDetail.rationaleTradeLead")}
          </p>
          <ul className="news-list">
            {summarizeTradeRationale(detail, t).map((line, i) => (
              <li key={`tr-${i}-${line.slice(0, 40)}`}>{line}</li>
            ))}
          </ul>
        </div>
      </div>
    </ContentPanel>
  );
}
