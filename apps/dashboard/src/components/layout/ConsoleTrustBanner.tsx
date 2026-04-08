"use client";

import Link from "next/link";

import { useI18n } from "@/components/i18n/I18nProvider";
import { consolePath } from "@/lib/console-paths";

export function ConsoleTrustBanner() {
  const { t } = useI18n();
  return (
    <div className="console-trust-banner" role="status">
      <strong>{t("console.trustBanner.strong")}</strong>{" "}
      {t("console.trustBanner.text")}
      <p className="muted small console-trust-banner__links" style={{ marginTop: 8 }}>
        <Link href={consolePath("diagnostics")}>
          {t("console.trustBanner.linkDiagnostics")}
        </Link>
        {" · "}
        <Link href={consolePath("self-healing")}>
          {t("console.trustBanner.linkSelfHealing")}
        </Link>
        {" · "}
        <Link href={consolePath("health")}>{t("console.trustBanner.linkHealth")}</Link>
      </p>
    </div>
  );
}
