"use client";

import { useI18n } from "@/components/i18n/I18nProvider";

/** Erste Tab-Stop: Springt zum Hauptinhalt (WCAG 2.4.1). */
export function SkipToMainLink() {
  const { t } = useI18n();
  return (
    <a href="#dash-main-content" className="skip-to-main">
      {t("ui.skipToMain")}
    </a>
  );
}
