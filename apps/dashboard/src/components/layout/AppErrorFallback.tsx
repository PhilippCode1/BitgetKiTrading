"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo } from "react";
import { useSearchParams } from "next/navigation";

import { useI18n } from "@/components/i18n/I18nProvider";
import { ProductMessageCard } from "@/components/product-messages/ProductMessageCard";
import { buildProductMessageFromFetchError } from "@/lib/product-messages";
import { CONSOLE_BASE, PORTAL_BASE } from "@/lib/console-paths";

type Props = Readonly<{
  error: Error & { digest?: string };
  reset: () => void;
  /** Setzt „Zur Konsole“-Link (Root-error.tsx). */
  showConsoleLink?: boolean;
  /** Kunden-Route-Group: Link zum Portal. */
  showCustomerPortalLink?: boolean;
}>;

type InnerProps = Props & Readonly<{ showTechnical: boolean }>;

/**
 * Liest `?diagnostic=1` — muss in {@link Suspense} hängen.
 */
function useDiagnosticMode(): boolean {
  const sp = useSearchParams();
  const d = sp?.get("diagnostic");
  return d === "1" || d === "true";
}

function AppErrorContent({
  error,
  reset,
  showConsoleLink,
  showCustomerPortalLink,
  showTechnical,
}: InnerProps) {
  const { t } = useI18n();

  useEffect(() => {
    console.error(error);
  }, [error]);

  const productMessage = useMemo(
    () => buildProductMessageFromFetchError(error, t),
    [error, t],
  );

  return (
    <div className="app-error-fallback">
      <div className="app-error-fallback__card panel" role="alert">
        <ProductMessageCard
          className="app-error-fallback__message"
          message={productMessage}
          showTechnical={showTechnical}
          t={t}
          showActions={false}
          situationExplain={false}
        />
        {error.digest ? (
          <p className="muted small mono-small app-error-fallback__digest">
            {t("ui.appError.digestPrefix")} {error.digest}
          </p>
        ) : null}
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
          {showCustomerPortalLink ? (
            <Link href={PORTAL_BASE} className="public-btn ghost">
              {t("ui.appError.openCustomerPortal")}
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function AppErrorDiagnosticBody(props: Props) {
  const showTech = useDiagnosticMode();
  return <AppErrorContent {...props} showTechnical={showTech} />;
}

/**
 * Gemeinsame Fehler-UI für App-Router `error.tsx`.
 * Klassifiziert den Fehler und nutzt `productMessage.fetch.*` (kein Roh-`error.message` im Fliesstext).
 * Technik nur bei `?diagnostic=1` bzw. in der Klappe in {@link ProductMessageCard}.
 */
export function AppErrorFallback({
  error,
  reset,
  showConsoleLink,
  showCustomerPortalLink,
}: Props) {
  return (
    <Suspense
      fallback={
        <AppErrorContent
          error={error}
          reset={reset}
          showConsoleLink={showConsoleLink}
          showCustomerPortalLink={showCustomerPortalLink}
          showTechnical={false}
        />
      }
    >
      <AppErrorDiagnosticBody
        error={error}
        reset={reset}
        showConsoleLink={showConsoleLink}
        showCustomerPortalLink={showCustomerPortalLink}
      />
    </Suspense>
  );
}
