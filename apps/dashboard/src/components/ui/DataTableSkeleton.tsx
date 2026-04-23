"use client";

import { useI18n } from "@/components/i18n/I18nProvider";

type Props = Readonly<{
  columnCount: number;
  rowCount?: number;
  /** Aria-Text (i18n-Key), z. B. ui.emptyState.tableLoading. */
  ariaLabelKey: string;
  /** Zusätzlich auf dem Desktop-Tabellen-Wrapper, z. B. signals-table-wide. */
  tableWrapClassName?: string;
  /** Zusätzlich auf der Mobile-Stack-Liste, z. B. signals-mobile-cards. */
  listClassName?: string;
}>;

/**
 * Doppel-Layout (Mobile-Listen-Skeleton + Desktop-Tabellen-Skeleton) passend zu den Operator-Tabellen.
 */
export function DataTableSkeleton({
  columnCount,
  rowCount = 6,
  ariaLabelKey,
  tableWrapClassName = "",
  listClassName = "",
}: Props) {
  const { t } = useI18n();
  const label = t(ariaLabelKey);
  return (
    <div
      className="data-table-skeleton-root"
      role="status"
      aria-busy
      aria-label={label}
    >
      <ul
        className={["console-stack-list", "data-table-skeleton--mobile", "console-mobile-only", listClassName]
          .filter(Boolean)
          .join(" ")}
        aria-hidden
      >
        {Array.from({ length: Math.min(3, rowCount) }).map((_, i) => (
          <li
            key={`m-${i}`}
            className="console-stack-card data-table-skeleton__card"
          >
            <div className="data-table-skeleton__shimmer data-table-skeleton__bar--title" />
            <div className="data-table-skeleton__shimmer data-table-skeleton__bar" />
            <div className="data-table-skeleton__shimmer data-table-skeleton__bar data-table-skeleton__bar--short" />
            <div className="data-table-skeleton__row">
              <div className="data-table-skeleton__shimmer data-table-skeleton__bar data-table-skeleton__bar--tiny" />
              <div className="data-table-skeleton__shimmer data-table-skeleton__bar data-table-skeleton__bar--tiny" />
            </div>
          </li>
        ))}
      </ul>
      <div
        className={["table-wrap", "console-desktop-only", tableWrapClassName]
          .filter(Boolean)
          .join(" ")}
        aria-hidden
      >
        <div className="data-table-skeleton__wrap">
          <table className="data-table data-table--dense" aria-hidden>
            <thead>
              <tr>
                {Array.from({ length: columnCount }).map((_, c) => (
                  <th key={`h-${c}`} scope="col">
                    <span
                      className="data-table-skeleton__shimmer data-table-skeleton__th"
                    />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: rowCount }).map((_, r) => (
                <tr key={`r-${r}`}>
                  {Array.from({ length: columnCount }).map((_, c) => (
                    <td key={`c-${r}-${c}`}>
                      <span
                        className="data-table-skeleton__shimmer data-table-skeleton__td"
                        style={{ width: `${55 + (c * 5 + r) % 35}%` }}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
