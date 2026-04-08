import { Suspense, type CSSProperties, type ReactNode } from "react";

import { ConsoleFetchNoticeActions } from "@/components/console/ConsoleFetchNoticeActions";
import { ProductMessageCard } from "@/components/product-messages/ProductMessageCard";
import type { TranslateFn } from "@/lib/user-facing-fetch-error";
import { buildProductMessageFromFetchError } from "@/lib/product-messages";

type NoticeProps = Readonly<{
  variant?: "soft" | "alert";
  /** Zeile 1: nur Titel */
  title?: string;
  /** Optional: „Lead:“ vor dem Titel (ein Absatz) */
  titlePrefix?: string;
  body?: string;
  refreshHint?: string;
  /** Zusatz am Ende der Refresh-Zeile (z. B. Reconnect-Hinweis) */
  refreshExtra?: string;
  technical?: string | null;
  showTechnical?: boolean;
  diagnosticSummaryLabel?: string;
  /** Schnellaktionen — Client-Insel mit Suspense */
  showStateActions?: boolean;
  /**
   * Zusätzlicher Wrapper um Aktionen (Abstand wie Live-Terminal).
   * Standard: false, damit bestehende PanelDataIssue-Layouts gleich bleiben.
   */
  wrapActions?: boolean;
  className?: string;
  style?: CSSProperties;
  /** Zusatzinhalt unter Body (z. B. Aufzählung Demo-Daten) */
  children?: ReactNode;
}>;

function joinTitle(
  prefix: string | undefined,
  title: string | undefined,
): string | null {
  const p = (prefix ?? "").trim();
  const t = (title ?? "").trim();
  if (p && t) return `${p}: ${t}`;
  if (t) return t;
  if (p) return p;
  return null;
}

function joinRefresh(
  hint: string | undefined,
  extra: string | undefined,
): string | null {
  const h = (hint ?? "").trim();
  const e = (extra ?? "").trim();
  if (h && e) return `${h} ${e}`;
  if (h) return h;
  if (e) return e;
  return null;
}

/**
 * Produktiver Hinweis statt Roh-HTTP/Gateway-String im Haupt-UI.
 * Zentrale Struktur für Fetch-Fehler, Demo-Banner und ähnliche Statusblöcke.
 */
export function ConsoleFetchNotice({
  variant = "soft",
  title,
  titlePrefix,
  body,
  refreshHint,
  refreshExtra,
  technical,
  showTechnical,
  diagnosticSummaryLabel,
  showStateActions = false,
  wrapActions = false,
  className = "",
  style,
  children,
}: NoticeProps) {
  const titleLine = joinTitle(titlePrefix, title);
  const refreshLine = joinRefresh(refreshHint, refreshExtra);
  const rootClass = [
    "console-fetch-notice",
    `console-fetch-notice--${variant}`,
    className.trim(),
  ]
    .filter(Boolean)
    .join(" ");

  const actions = showStateActions ? (
    wrapActions ? (
      <div className="console-fetch-notice-actions-wrap">
        <Suspense fallback={null}>
          <ConsoleFetchNoticeActions />
        </Suspense>
      </div>
    ) : (
      <Suspense fallback={null}>
        <ConsoleFetchNoticeActions />
      </Suspense>
    )
  ) : null;

  return (
    <div className={rootClass} role="status" style={style}>
      {titleLine ? (
        <p className="console-fetch-notice__title">{titleLine}</p>
      ) : null}
      {body ? (
        <p className="console-fetch-notice__body muted small">{body}</p>
      ) : null}
      {children}
      {refreshLine ? (
        <p className="console-fetch-notice__refresh muted small">
          {refreshLine}
        </p>
      ) : null}
      {actions}
      {showTechnical && technical ? (
        <details className="console-fetch-notice__diag small">
          <summary className="console-fetch-notice__diag-sum">
            {diagnosticSummaryLabel ?? ""}
          </summary>
          <pre className="console-fetch-notice__pre">{technical}</pre>
        </details>
      ) : null}
    </div>
  );
}

type PanelProps = Readonly<{
  err: string | null;
  diagnostic: boolean;
  t: TranslateFn;
  variant?: "soft" | "alert";
}>;

/** Wrapper: Roh-Fehler aus API → Klassifizierung + optional Diagnose-Block. */
export function PanelDataIssue({
  err,
  diagnostic,
  t,
  variant = "soft",
}: PanelProps) {
  if (!err) return null;
  try {
    const payload = new Error(err);
    const msg = buildProductMessageFromFetchError(payload, t);
    return (
      <ProductMessageCard
        message={msg}
        showTechnical={diagnostic}
        t={t}
        className={`panel-data-issue panel-data-issue--${variant}`}
      />
    );
  } catch {
    return (
      <ConsoleFetchNotice
        variant={variant}
        title={t("errors.generic")}
        body={String(err)}
        refreshHint={t("ui.refreshHint")}
        technical={String(err)}
        showTechnical={diagnostic}
        diagnosticSummaryLabel={t("ui.diagnostic.summary")}
        showStateActions
      />
    );
  }
}
