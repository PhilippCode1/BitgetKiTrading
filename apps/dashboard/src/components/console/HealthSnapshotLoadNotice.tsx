import Link from "next/link";

import { SystemStatusCard } from "@/components/system-comms/SystemStatusCard";
import { SystemStatusCardActions } from "@/components/system-comms/SystemStatusCardActions";
import type { GatewayFetchErrorInfo } from "@/lib/gateway-fetch-errors";
import { formatTechnicalDetailForPre } from "@/lib/server-payload-text";
import { consolePath } from "@/lib/console-paths";
import type { TranslateFn } from "@/lib/user-facing-fetch-error";

type Props = Readonly<{
  error: GatewayFetchErrorInfo | null;
  diagnostic: boolean;
  t: TranslateFn;
}>;

/**
 * Wenn GET /v1/system/health auf einer Seite scheitert, aber der Rest der Seite lädt:
 * strukturierte Systemkommunikation (Phase, Schritte, Self-Healing, Experten-Klappe).
 */
export function HealthSnapshotLoadNotice({ error, diagnostic, t }: Props) {
  if (!error) return null;
  return (
    <div className="health-snapshot-load-notice">
      <SystemStatusCard
        phase="blocked"
        titleKey="systemComms.healthSnapshot.title"
        bodyKey="systemComms.healthSnapshot.body"
        stepKeys={[
          "systemComms.healthSnapshot.step1",
          "systemComms.healthSnapshot.step2",
          "systemComms.healthSnapshot.step3",
        ]}
        technical={formatTechnicalDetailForPre(error.technical)}
        showTechnical={diagnostic}
        diagnosticSummaryLabel={t("ui.diagnostic.summary")}
        t={t}
      >
        <p className="muted small system-comms-card__cta-row">
          <Link href={consolePath("self-healing")} className="public-btn ghost">
            {t("ui.healthSnapshot.selfHealingCta")}
          </Link>
        </p>
        <SystemStatusCardActions />
      </SystemStatusCard>
    </div>
  );
}
