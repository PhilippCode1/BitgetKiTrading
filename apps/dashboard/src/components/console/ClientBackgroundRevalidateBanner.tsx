"use client";

import { useCallback, useEffect, useState } from "react";

import { SystemStatusCard } from "@/components/system-comms/SystemStatusCard";
import { SystemStatusCardActions } from "@/components/system-comms/SystemStatusCardActions";
import { useI18n } from "@/components/i18n/I18nProvider";

type Detail = Readonly<{ bffPath: string; message: string }>;

const EVENT = "dashboard-bff-background-revalidate-failed";

/**
 * Stale-while-revalidate: bei fehlgeschlagenem Nachladen weiterhin Cache zeigen,
 * aber klar kommunizieren (Phase „instabil“, Schritte, Experten-Details, ausblendbar).
 */
export function ClientBackgroundRevalidateBanner() {
  const { t } = useI18n();
  const [detail, setDetail] = useState<Detail | null>(null);

  const onFail = useCallback((ev: Event) => {
    const ce = ev as CustomEvent<Detail>;
    const d = ce.detail;
    if (d?.bffPath) setDetail(d);
  }, []);

  useEffect(() => {
    window.addEventListener(EVENT, onFail);
    return () => window.removeEventListener(EVENT, onFail);
  }, [onFail]);

  if (!detail) return null;

  const technical = `${detail.bffPath}\n${detail.message}`;

  return (
    <div
      className="client-bg-revalidate-banner"
      role="alert"
      aria-live="polite"
    >
      <SystemStatusCard
        phase="unstable"
        titleKey="systemComms.backgroundRefresh.title"
        bodyKey="systemComms.backgroundRefresh.body"
        stepKeys={[
          "systemComms.backgroundRefresh.step1",
          "systemComms.backgroundRefresh.step2",
          "systemComms.backgroundRefresh.step3",
        ]}
        technical={technical}
        showTechnical
        diagnosticSummaryLabel={t("ui.diagnostic.summary")}
        t={t}
      >
        <SystemStatusCardActions />
        <div className="client-bg-revalidate-banner__dismiss">
          <button
            type="button"
            className="public-btn ghost"
            onClick={() => setDetail(null)}
          >
            {t("ui.dismiss")}
          </button>
        </div>
      </SystemStatusCard>
    </div>
  );
}
