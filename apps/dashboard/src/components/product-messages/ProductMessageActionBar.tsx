"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import { consolePath } from "@/lib/console-paths";

/**
 * Aktionsleiste zu Produktmeldungen — konsistent über die Konsole.
 * „Selbstheilung“ = Server-Komponenten neu einlesen ohne vollständigen Tab-Reload.
 */
export function ProductMessageActionBar() {
  const { t } = useI18n();
  const router = useRouter();
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
      className="product-message-card__actions"
      role="group"
      aria-label={t("productMessage.actions.groupAria")}
    >
      <button
        type="button"
        className="public-btn ghost"
        onClick={() => router.refresh()}
      >
        {t("productMessage.actions.reloadRegion")}
      </button>
      <button
        type="button"
        className="public-btn ghost"
        onClick={() => window.location.reload()}
      >
        {t("productMessage.actions.fullReload")}
      </button>
      <Link
        href={consolePath("health")}
        className="public-btn ghost"
        scroll={false}
      >
        {t("productMessage.actions.openHealth")}
      </Link>
      <a
        href="/api/dashboard/edge-status"
        target="_blank"
        rel="noreferrer"
        className="public-btn ghost"
      >
        {t("productMessage.actions.edgeDiagnostics")}
      </a>
      <Link href={diagnosticHref} className="public-btn ghost" scroll={false}>
        {t("productMessage.actions.openTechnical")}
      </Link>
    </div>
  );
}
