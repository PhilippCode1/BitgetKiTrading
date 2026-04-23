"use client";

import { useI18n } from "@/components/i18n/I18nProvider";
import { DataTableSkeleton } from "@/components/ui/DataTableSkeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatNum, formatTsMs } from "@/lib/format";
import type { PaperOpenPosition } from "@/lib/types";

type Props = Readonly<{
  positions: PaperOpenPosition[];
  isLoading?: boolean;
}>;

export function OpenPositionsTable({ positions, isLoading = false }: Props) {
  const { t } = useI18n();
  const dash = t("tables.paperOpen.emDash");
  if (isLoading) {
    return (
      <DataTableSkeleton
        columnCount={9}
        ariaLabelKey="ui.emptyState.tableLoading"
      />
    );
  }
  if (positions.length === 0) {
    return (
      <EmptyState
        icon="wallet"
        titleKey="tables.paperOpen.emptyTitle"
        descriptionKey="tables.paperOpen.emptyDescription"
        nextStepKey="tables.paperOpen.emptyNextStep"
      />
    );
  }
  return (
    <>
      <ul
        className="console-stack-list console-mobile-only"
        aria-label={t("pages.paper.openPositionsTitle")}
      >
        {positions.map((p) => (
          <li key={`m-${p.position_id}`} className="console-stack-card">
            <p className="console-stack-card__title">{p.symbol}</p>
            <div className="console-stack-card__dl">
              <div>
                <span className="console-stack-card__k">
                  {t("tables.paperOpen.thSide")}
                </span>
                <span className="console-stack-card__v">{p.side}</span>
              </div>
              <div>
                <span className="console-stack-card__k">
                  {t("tables.paperOpen.thQty")}
                </span>
                <span className="console-stack-card__v">{p.qty_base}</span>
              </div>
              <div>
                <span className="console-stack-card__k">
                  {t("tables.paperOpen.thUpnl")}
                </span>
                <span
                  className={`console-stack-card__v ${
                    p.unrealized_pnl_usdt >= 0 ? "dir-long" : "dir-short"
                  }`}
                >
                  {formatNum(p.unrealized_pnl_usdt, 4)}
                </span>
              </div>
              <div>
                <span className="console-stack-card__k">
                  {t("tables.paperOpen.thLev")}
                </span>
                <span className="console-stack-card__v">{p.leverage}x</span>
              </div>
              <div>
                <span className="console-stack-card__k">
                  {t("tables.paperOpen.thOpened")}
                </span>
                <span className="console-stack-card__v mono-small">
                  {formatTsMs(p.opened_ts_ms)}
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
              <th>{t("tables.paperOpen.thSymbol")}</th>
              <th>{t("tables.paperOpen.thSide")}</th>
              <th>{t("tables.paperOpen.thQty")}</th>
              <th>{t("tables.paperOpen.thEntry")}</th>
              <th>{t("tables.paperOpen.thLev")}</th>
              <th>{t("tables.paperOpen.thCap")}</th>
              <th>{t("tables.paperOpen.thMark")}</th>
              <th>{t("tables.paperOpen.thUpnl")}</th>
              <th>{t("tables.paperOpen.thOpened")}</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <tr key={p.position_id}>
                <td>{p.symbol}</td>
                <td>{p.side}</td>
                <td>{p.qty_base}</td>
                <td>{p.entry_price_avg}</td>
                <td>{p.leverage}x</td>
                <td>
                  {Array.isArray(p.leverage_allocator?.binding_cap_names)
                    ? p.leverage_allocator.binding_cap_names.join(", ")
                    : dash}
                </td>
                <td>
                  {p.mark_price != null ? formatNum(p.mark_price, 2) : dash}
                </td>
                <td
                  className={
                    p.unrealized_pnl_usdt >= 0 ? "dir-long" : "dir-short"
                  }
                >
                  {formatNum(p.unrealized_pnl_usdt, 4)}
                </td>
                <td>{formatTsMs(p.opened_ts_ms)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
