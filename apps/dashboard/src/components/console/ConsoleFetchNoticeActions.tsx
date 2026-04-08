"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import { consolePath } from "@/lib/console-paths";

/**
 * Wiederholbare Aktionen bei Ladefehlern / Leerzuständen (Reload, Health, Verbindungscheck, Diagnose).
 * Sichtbare Texte ohne Ro-URLs; der Verbindungscheck öffnet die JSON-Diagnose in neuem Tab.
 */
export function ConsoleFetchNoticeActions() {
  const { t } = useI18n();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const diagnosticHref = useMemo(() => {
    const p = new URLSearchParams(searchParams.toString());
    p.set("diagnostic", "1");
    const q = p.toString();
    return q ? `${pathname}?${q}` : `${pathname}?diagnostic=1`;
  }, [pathname, searchParams]);

  return (
    <div
      className="console-fetch-notice-actions"
      role="group"
      aria-label={t("ui.stateActions.groupAria")}
    >
      <button
        type="button"
        className="public-btn ghost"
        onClick={() => window.location.reload()}
      >
        {t("ui.stateActions.retry")}
      </button>
      <Link
        href={consolePath("health")}
        className="public-btn ghost"
        scroll={false}
      >
        {t("ui.stateActions.openHealth")}
      </Link>
      <a
        href="/api/dashboard/edge-status"
        target="_blank"
        rel="noreferrer"
        className="public-btn ghost"
      >
        {t("ui.issueCenter.checkConnection")}
      </a>
      <Link href={diagnosticHref} className="public-btn ghost" scroll={false}>
        {t("ui.stateActions.openDiagnostic")}
      </Link>
    </div>
  );
}
