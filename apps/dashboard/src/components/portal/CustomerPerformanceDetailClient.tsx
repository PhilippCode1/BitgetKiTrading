"use client";

import Link from "next/link";
import { useMemo } from "react";

import { ProductLineChart } from "@/components/chart/ProductLineChart";
import { useI18n } from "@/components/i18n/I18nProvider";
import { portalPath } from "@/lib/console-paths";

type Props = Readonly<{
  periodId: string;
}>;

/**
 * Einfacher Equity-Verlauf (leichtes Chart-Init) fuer Kunden-Detail — gleiche lib wie Konsole, ohne Marktdaten-Pipeline.
 */
export function CustomerPerformanceDetailClient({ periodId }: Props) {
  const { t } = useI18n();
  const series = useMemo(
    () =>
      [1, 2, 3, 4, 5, 6, 7, 8].map((i) => ({
        time_s: 1_700_000_000 + i * 86_400,
        value: 10_000 + i * 120.5,
      })),
    [],
  );

  return (
    <div
      className="panel"
      data-testid="customer-performance-detail"
    >
      <p className="muted" style={{ marginTop: 0 }}>
        <Link
          className="public-btn ghost"
          href={portalPath("performance")}
        >
          {t("customerPortal.performanceDetail.back")}
        </Link>
      </p>
      <h1 style={{ marginTop: 0 }}>
        {t("customerPortal.performanceDetail.title", {
          id: periodId,
        })}
      </h1>
      <p className="muted">{t("customerPortal.performanceDetail.lead")}</p>
      <h2 style={{ fontSize: "1rem", margin: "20px 0 8px" }}>
        {t("customerPortal.performanceDetail.chartCaption")}
      </h2>
      <ProductLineChart
        series={series}
        height={220}
        ariaLabel={t("customerPortal.performanceDetail.chartAria")}
        className="customer-perf-line-chart"
      />
      <p
        className="muted small"
        style={{ marginTop: 12, marginBottom: 0 }}
      >
        {t("customerPortal.performanceDetail.demoNote")}
      </p>
    </div>
  );
}
