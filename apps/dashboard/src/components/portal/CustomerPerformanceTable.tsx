"use client";

import Link from "next/link";

import { useI18n } from "@/components/i18n/I18nProvider";
import { portalPath } from "@/lib/console-paths";

const MOCK_PERIODS = [
  { id: "e2e-mock-1", labelKey: "customerPortal.performancePage.tableRow1" },
  { id: "e2e-mock-2", labelKey: "customerPortal.performancePage.tableRow2" },
] as const;

/**
 * Demo-Performance-Liste (ohne Live-API) — ermoeglich Endkunden-E2E: Zeile -> Detail-Route.
 */
export function CustomerPerformanceTable() {
  const { t } = useI18n();
  return (
    <div
      className="table-wrap"
      data-testid="customer-performance-table"
      style={{ marginTop: 16 }}
    >
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">{t("customerPortal.performancePage.colPeriod")}</th>
            <th scope="col">{t("customerPortal.performancePage.colView")}</th>
          </tr>
        </thead>
        <tbody>
          {MOCK_PERIODS.map((row) => (
            <tr
              key={row.id}
              data-e2e-performance-row={row.id}
            >
              <td>{t(row.labelKey)}</td>
              <td>
                <Link
                  className="public-btn ghost"
                  href={portalPath(`performance/${row.id}`)}
                >
                  {t("customerPortal.performancePage.openDetail")}
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
