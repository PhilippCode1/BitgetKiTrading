"use client";

import { useI18n } from "@/components/i18n/I18nProvider";

/**
 * Neutraler Ladezustand fuer route-level loading.tsx (i18n ueber Client-Insel).
 */
export function PageLoadingSkeleton() {
  const { t } = useI18n();
  return (
    <div
      className="page-loading-skeleton"
      aria-busy="true"
      aria-live="polite"
      aria-label={t("ui.pageLoading.ariaLabel")}
    >
      <div className="page-loading-skeleton__bar" />
      <div className="page-loading-skeleton__lines">
        <span />
        <span />
        <span className="page-loading-skeleton__lines--short" />
      </div>
      <p className="muted small page-loading-skeleton__hint">
        {t("ui.pageLoading.hint")}
      </p>
    </div>
  );
}
