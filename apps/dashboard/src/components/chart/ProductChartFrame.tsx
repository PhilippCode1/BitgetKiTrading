"use client";

import type { ReactNode } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";

export type ProductChartOverlay = "none" | "loading" | "error" | "empty";

type Props = Readonly<{
  overlay: ProductChartOverlay;
  /** Nutzer- oder Server-Text fuer error/empty */
  message?: string | null;
  /** Chart-Canvas (div mit Ref) */
  children: ReactNode;
  className?: string;
  /** Mindesthoehe in px — stabil fuer CLS */
  minHeight?: number;
  /** A11y: Kurzbeschreibung des Chart-Inhalts */
  ariaLabel?: string;
}>;

/**
 * Gemeinsamer Rahmen: Produkt-Shell (Rand, Radius, Schatten) + Lade-/Fehler-/Leer-Overlay.
 * Nur Client — lightweight-charts laeuft nicht unter SSR.
 */
export function ProductChartFrame({
  overlay,
  message,
  children,
  className = "",
  minHeight = 280,
  ariaLabel,
}: Props) {
  const { t } = useI18n();
  const showOverlay = overlay !== "none";

  return (
    <div
      className={`product-chart-frame ${className}`.trim()}
      style={{ minHeight }}
      role="region"
      aria-label={ariaLabel ?? t("ui.chart.defaultAria")}
    >
      <div className="product-chart-frame__canvas">{children}</div>
      {showOverlay ? (
        <div
          className={`product-chart-frame__overlay product-chart-frame__overlay--${overlay}`}
          role="status"
          aria-live="polite"
        >
          {overlay === "loading" ? (
            <div className="product-chart-skeleton" aria-hidden>
              <div className="product-chart-skeleton__shimmer" />
            </div>
          ) : null}
          {overlay === "error" ? (
            <p className="product-chart-frame__message">
              {message ?? t("ui.chart.errorGeneric")}
            </p>
          ) : null}
          {overlay === "empty" ? (
            <p className="product-chart-frame__message">
              {message ?? t("ui.chart.emptyGeneric")}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
