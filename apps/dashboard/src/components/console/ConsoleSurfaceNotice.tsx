import type { CSSProperties, ReactNode } from "react";

import { ConsoleFetchNotice } from "@/components/console/ConsoleFetchNotice";
import type { TranslateFn } from "@/lib/user-facing-fetch-error";

export type ConsoleSurfaceNoticeProps = Readonly<{
  t: TranslateFn;
  variant?: "soft" | "alert";
  titleKey: string;
  bodyKey?: string;
  body?: string | null;
  titlePrefixKey?: string;
  refreshKey?: string;
  refreshHint?: string | null;
  refreshExtraKey?: string;
  refreshExtra?: string | null;
  showStateActions?: boolean;
  wrapActions?: boolean;
  technical?: string | null;
  showTechnical?: boolean;
  diagnosticSummaryLabel?: string;
  diagnosticSummaryLabelKey?: string;
  className?: string;
  style?: CSSProperties;
  children?: ReactNode;
}>;

/**
 * Server-Komponente: Status-Hinweis mit i18n-Keys statt duplizierter Markup-Struktur.
 * Nutzt dieselbe Darstellung wie PanelDataIssue (ConsoleFetchNotice).
 */
export function ConsoleSurfaceNotice({
  t,
  variant = "soft",
  titleKey,
  bodyKey,
  body,
  titlePrefixKey,
  refreshKey,
  refreshHint,
  refreshExtraKey,
  refreshExtra,
  showStateActions = false,
  wrapActions = false,
  technical,
  showTechnical = false,
  diagnosticSummaryLabel,
  diagnosticSummaryLabelKey,
  className = "",
  style,
  children,
}: ConsoleSurfaceNoticeProps) {
  const bodyText =
    body != null && String(body).trim() !== ""
      ? String(body)
      : bodyKey
        ? t(bodyKey)
        : undefined;
  const summaryLabel =
    diagnosticSummaryLabel ??
    (diagnosticSummaryLabelKey ? t(diagnosticSummaryLabelKey) : undefined);

  return (
    <ConsoleFetchNotice
      variant={variant}
      titlePrefix={titlePrefixKey ? t(titlePrefixKey) : undefined}
      title={t(titleKey)}
      body={bodyText}
      refreshHint={refreshHint ?? (refreshKey ? t(refreshKey) : undefined)}
      refreshExtra={
        refreshExtra ?? (refreshExtraKey ? t(refreshExtraKey) : undefined)
      }
      technical={technical}
      showTechnical={showTechnical}
      diagnosticSummaryLabel={summaryLabel}
      showStateActions={showStateActions}
      wrapActions={wrapActions}
      className={className}
      style={style}
    >
      {children}
    </ConsoleFetchNotice>
  );
}
