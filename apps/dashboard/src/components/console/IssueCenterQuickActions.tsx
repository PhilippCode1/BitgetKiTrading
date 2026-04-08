"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import { consolePath } from "@/lib/console-paths";

/**
 * Schnellaktionen fuer das zentrale Statuszentrum (Client: Reload + aktuelle Query fuer Diagnose).
 */
export function IssueCenterQuickActions() {
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
      className="issue-center-quick-actions"
      role="group"
      aria-label={t("ui.issueCenter.actionsLabel")}
    >
      <a
        href="/api/dashboard/edge-status"
        target="_blank"
        rel="noreferrer"
        className="issue-center-action"
      >
        {t("ui.issueCenter.checkConnection")}
      </a>
      <button
        type="button"
        className="issue-center-action"
        onClick={() => window.location.reload()}
      >
        {t("ui.issueCenter.reload")}
      </button>
      <Link
        href={diagnosticHref}
        className="issue-center-action"
        scroll={false}
      >
        {t("ui.issueCenter.openDiagnostic")}
      </Link>
      <Link href={consolePath("health")} className="issue-center-action">
        {t("ui.issueCenter.showSetup")}
      </Link>
    </div>
  );
}
