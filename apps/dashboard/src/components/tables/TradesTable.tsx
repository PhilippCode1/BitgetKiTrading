"use client";

import { useI18n } from "@/components/i18n/I18nProvider";
import { DataTableSkeleton } from "@/components/ui/DataTableSkeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatNum, formatTsMs } from "@/lib/format";
import type { PaperTradeRow } from "@/lib/types";

type Props = Readonly<{
  trades: PaperTradeRow[];
  isLoading?: boolean;
}>;

export function TradesTable({ trades, isLoading = false }: Props) {
  const { t } = useI18n();
  const dash = t("tables.paperTrades.emDash");
  if (isLoading) {
    return (
      <DataTableSkeleton
        columnCount={8}
        ariaLabelKey="ui.emptyState.tableLoading"
      />
    );
  }
  if (trades.length === 0) {
    return (
      <EmptyState
        icon="activity"
        titleKey="tables.paperTrades.emptyTitle"
        descriptionKey="tables.paperTrades.emptyDescription"
        nextStepKey="tables.paperTrades.emptyNextStep"
      />
    );
  }
  return (
    <>
      <ul
        className="console-stack-list console-mobile-only"
        aria-label={t("pages.paper.recentTradesTitle")}
      >
        {trades.map((tr) => (
          <li key={`m-${tr.position_id}`} className="console-stack-card">
            <div className="console-stack-card__meta">
              <span className="mono-small">{formatTsMs(tr.closed_ts_ms)}</span>
              <span className="muted small">{tr.symbol}</span>
            </div>
            <div className="console-stack-card__dl">
              <div>
                <span className="console-stack-card__k">
                  {t("tables.paperTrades.thSide")}
                </span>
                <span className="console-stack-card__v">{tr.side}</span>
              </div>
              <div>
                <span className="console-stack-card__k">
                  {t("tables.paperTrades.thPnl")}
                </span>
                <span
                  className={`console-stack-card__v ${
                    (tr.pnl_net_usdt ?? 0) >= 0 ? "dir-long" : "dir-short"
                  }`}
                >
                  {formatNum(tr.pnl_net_usdt ?? 0, 4)}
                </span>
              </div>
              <div>
                <span className="console-stack-card__k">
                  {t("tables.paperTrades.thFees")}
                </span>
                <span className="console-stack-card__v">
                  {formatNum(tr.fees_total_usdt, 4)}
                </span>
              </div>
              <div>
                <span className="console-stack-card__k">
                  {t("tables.paperTrades.thReason")}
                </span>
                <span className="console-stack-card__v">
                  {tr.reason_closed ?? dash}
                </span>
              </div>
            </div>
          </li>
        ))}
      </ul>
      <div className="table-wrap console-desktop-only">
        <table className="data-table">
          <thead>
            <tr>
              <th>{t("tables.paperTrades.thClosed")}</th>
              <th>{t("tables.paperTrades.thSymbol")}</th>
              <th>{t("tables.paperTrades.thSide")}</th>
              <th>{t("tables.paperTrades.thLev")}</th>
              <th>{t("tables.paperTrades.thPnl")}</th>
              <th>{t("tables.paperTrades.thFees")}</th>
              <th>{t("tables.paperTrades.thFunding")}</th>
              <th>{t("tables.paperTrades.thReason")}</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((tr) => (
              <tr key={tr.position_id}>
                <td>{formatTsMs(tr.closed_ts_ms)}</td>
                <td>{tr.symbol}</td>
                <td>{tr.side}</td>
                <td>
                  {typeof tr.leverage_allocator?.recommended_leverage ===
                  "number"
                    ? `${tr.leverage_allocator.recommended_leverage}x`
                    : dash}
                </td>
                <td>{formatNum(tr.pnl_net_usdt, 4)}</td>
                <td>{formatNum(tr.fees_total_usdt, 4)}</td>
                <td>{formatNum(tr.funding_total_usdt, 4)}</td>
                <td>{tr.reason_closed ?? dash}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
