import Link from "next/link";

import { getCustomerPortalSummary } from "@/lib/customer-portal-summary";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { portalAccountPath } from "@/lib/console-paths";

export const dynamic = "force-dynamic";

export default async function CustomerPortalTrialPage() {
  const t = await getServerTranslator();
  const s = await getCustomerPortalSummary();
  const l = s.commerceLifecycle?.body;

  return (
    <div className="panel" data-e2e="customer-portal-trial">
      <h1 style={{ marginTop: 0 }}>{t("customerPortal.trialPage.title")}</h1>
      <p className="muted">{t("customerPortal.trialPage.lead")}</p>
      {l == null && (
        <p className="muted">{t("customerPortal.trialPage.unavailable")}</p>
      )}
      {l != null && (
        <dl
          className="muted"
          style={{ display: "grid", gap: 8, marginTop: 16, maxWidth: 520 }}
        >
          <div>
            <dt>
              <strong>{t("customerPortal.trialPage.status")}</strong>
            </dt>
            <dd style={{ margin: 0 }}>{l.status}</dd>
          </div>
          <div>
            <dt>
              <strong>{t("customerPortal.trialPage.trialEnds")}</strong>
            </dt>
            <dd style={{ margin: 0 }}>{l.trial.endsAt ?? "—"}</dd>
          </div>
          <div>
            <dt>
              <strong>{t("customerPortal.trialPage.clock")}</strong>
            </dt>
            <dd style={{ margin: 0 }}>
              {l.trial.clockActive
                ? t("customerPortal.trialPage.active")
                : t("customerPortal.trialPage.inactive")}
            </dd>
          </div>
        </dl>
      )}
      <p className="muted" style={{ marginTop: 24 }}>
        {t("customerPortal.trialPage.nextContract")}{" "}
        <Link className="public-link" href={portalAccountPath("billing")}>
          {t("customerPortal.trialPage.contractLink")}
        </Link>
        .
      </p>
    </div>
  );
}
