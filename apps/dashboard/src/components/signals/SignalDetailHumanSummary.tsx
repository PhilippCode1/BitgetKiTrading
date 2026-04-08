import { ContentPanel } from "@/components/ui/ContentPanel";
import { formatNum, formatPct01, formatTsMs } from "@/lib/format";
import { resolveTradeActionI18n } from "@/lib/signal-detail-trade-action";
import type { SignalDetail } from "@/lib/types";
import type { SignalExplainResponse } from "@/lib/types";

type Translate = (
  key: string,
  values?: Record<string, string | number>,
) => string;

type Props = Readonly<{
  detail: SignalDetail;
  explain: SignalExplainResponse | null;
  t: Translate;
}>;

/**
 * Schicht 1: Kurzfassung in Alltagssprache — keine Rohfeldnamen.
 */
export function SignalDetailHumanSummary({ detail, explain, t }: Props) {
  const taRef = resolveTradeActionI18n(detail.trade_action);
  const actionHuman = "vars" in taRef ? t(taRef.key, taRef.vars) : t(taRef.key);
  const shortFromApi = explain?.explain_short?.trim() ?? "";

  return (
    <ContentPanel className="signal-detail-human-summary">
      <h2 className="h3-quiet">{t("pages.signalsDetail.summaryTitle")}</h2>
      <p className="muted small">{t("pages.signalsDetail.summaryLead")}</p>
      <div className="signal-detail-human-summary__prose">
        <p>
          {t("pages.signalsDetail.summaryInstrument", {
            symbol: detail.symbol,
            timeframe: detail.timeframe,
            family:
              detail.market_family ??
              t("pages.signalsDetail.summaryFamilyUnknown"),
          })}
        </p>
        <p>
          {t("pages.signalsDetail.summaryDirection", {
            direction: detail.direction,
            strength: formatNum(detail.signal_strength_0_100, 1),
            probability: formatPct01(detail.probability_0_1),
          })}
        </p>
        <p>
          {t("pages.signalsDetail.summaryDecision", { action: actionHuman })}
        </p>
        {shortFromApi ? (
          <p className="signal-detail-human-summary__explain-hook">
            <strong>{t("pages.signalsDetail.summaryStoredShortLabel")}</strong>{" "}
            {shortFromApi}
          </p>
        ) : (
          <p className="muted small">
            {t("pages.signalsDetail.summaryNoShortYet")}
          </p>
        )}
        <p className="muted small signal-detail-human-summary__time">
          {t("pages.signalsDetail.summaryAnalysisTime", {
            ts: formatTsMs(detail.analysis_ts_ms),
          })}
        </p>
        <p className="muted small">
          {t("pages.signalsDetail.summaryGlossary")}
        </p>
      </div>
      <p className="signal-detail-human-summary__disclaimer">
        {t("pages.signalsDetail.summaryDisclaimer")}
      </p>
    </ContentPanel>
  );
}
