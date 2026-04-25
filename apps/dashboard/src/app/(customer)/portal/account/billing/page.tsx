import { getCustomerPortalSummary } from "@/lib/customer-portal-summary";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function CustomerAccountBillingPage() {
  const t = await getServerTranslator();
  const s = await getCustomerPortalSummary();
  const me = s.commerceCustomerMe?.body;
  return (
    <div className="panel" data-e2e="customer-portal-billing">
      <h1 style={{ marginTop: 0 }}>{t("customerPortal.accountBilling.title")}</h1>
      <p className="muted small" style={{ marginTop: 8 }}>
        {t("customerPortal.accountBilling.bffSource")}
      </p>
      <section style={{ marginTop: "1.5rem" }}>
        <h2 className="muted" style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>
          {t("customerPortal.accountBilling.contractHeading")}
        </h2>
        {me == null && <p className="muted">{t("customerPortal.placeholder")}</p>}
        {me != null && (
          <p className="muted" style={{ maxWidth: 560 }}>
            {t("customerPortal.accountBilling.planLine", {
              plan: me.plan.displayName ?? "—",
            })}
          </p>
        )}
      </section>
      <section style={{ marginTop: "1.5rem" }}>
        <h2 className="muted" style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>
          {t("customerPortal.accountBilling.billingHeading")}
        </h2>
        <p className="muted">{t("customerPortal.accountBilling.billingStub")}</p>
      </section>
    </div>
  );
}
