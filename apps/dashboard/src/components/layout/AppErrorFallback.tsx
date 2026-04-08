"use client";

import Link from "next/link";
import { useEffect } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import { CONSOLE_BASE } from "@/lib/console-paths";

type Props = Readonly<{
  error: Error & { digest?: string };
  reset: () => void;
  /** Link zur Konsole anzeigen (sinnvoll auf Root-Ebene). */
  showConsoleLink?: boolean;
}>;

/**
 * Gemeinsame Fehler-UI fuer App-Router error.tsx — klar formuliert, ohne leere Seite.
 * Rohe `error.message` nur in ausklappbaren technischen Details.
 */
export function AppErrorFallback({ error, reset, showConsoleLink }: Props) {
  const { t } = useI18n();

  useEffect(() => {
    console.error(error);
  }, [error]);

  const technical = error.message?.trim() || t("ui.appError.noDetail");

  return (
    <div className="app-error-fallback">
      <div className="app-error-fallback__card panel" role="alert">
        <h1 className="app-error-fallback__title">{t("ui.appError.title")}</h1>
        <p className="muted small app-error-fallback__msg">
          {t("ui.appError.body")}
        </p>
        {error.digest ? (
          <p className="muted small mono-small">
            {t("ui.appError.digestPrefix")} {error.digest}
          </p>
        ) : null}
        <details className="console-fetch-notice__diag small app-error-fallback__details">
          <summary className="console-fetch-notice__diag-sum">
            {t("ui.appError.technicalSummary")}
          </summary>
          <pre className="console-fetch-notice__pre">{technical}</pre>
        </details>
        <div className="app-error-fallback__actions">
          <button
            type="button"
            className="public-btn primary"
            onClick={() => reset()}
          >
            {t("ui.issueCenter.reload")}
          </button>
          <Link href="/" className="public-btn ghost">
            {t("ui.appError.home")}
          </Link>
          {showConsoleLink ? (
            <Link href={CONSOLE_BASE} className="public-btn ghost">
              {t("ui.appError.openConsole")}
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  );
}
