import { getCustomerPortalSummary } from "@/lib/customer-portal-summary";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

function isRecord(x: unknown): x is Record<string, unknown> {
  return x !== null && typeof x === "object" && !Array.isArray(x);
}

export default async function CustomerPortalExchangePage() {
  const t = await getServerTranslator();
  const s = await getCustomerPortalSummary();
  const i = s.commerceIntegrations?.body;

  return (
    <div className="panel" data-e2e="customer-portal-exchange">
      <h1 style={{ marginTop: 0 }}>{t("customerPortal.exchangePage.title")}</h1>
      <p className="muted">{t("customerPortal.exchangePage.lead")}</p>
      {i == null && (
        <p className="muted">{t("customerPortal.exchangePage.unavailable")}</p>
      )}
      {i != null && (
        <div className="muted" style={{ marginTop: 12 }}>
          <p>
            <strong>{t("customerPortal.exchangePage.brokerState")}</strong>{" "}
            {i.brokerState}
          </p>
          {i.brokerHintPublic && <p style={{ maxWidth: 600 }}>{i.brokerHintPublic}</p>}
          {i.bitgetEnv && isRecord(i.bitgetEnv) && "hint_public_de" in i.bitgetEnv && (
            <p style={{ maxWidth: 600 }}>
              {String((i.bitgetEnv as { hint_public_de?: unknown }).hint_public_de ?? "")}
            </p>
          )}
          <p className="small" style={{ marginTop: 16, opacity: 0.9 }}>
            {t("customerPortal.exchangePage.noKeys")}
          </p>
        </div>
      )}
    </div>
  );
}
