import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function CustomerAccountBillingPage() {
  const t = await getServerTranslator();
  return (
    <div className="panel">
      <h1 style={{ marginTop: 0 }}>{t("customerPortal.accountBilling.title")}</h1>
      <section style={{ marginTop: "1.5rem" }}>
        <h2 className="muted" style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>
          {t("customerPortal.accountBilling.contractHeading")}
        </h2>
        <p className="muted">{t("customerPortal.placeholder")}</p>
      </section>
      <section style={{ marginTop: "1.5rem" }}>
        <h2 className="muted" style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>
          {t("customerPortal.accountBilling.billingHeading")}
        </h2>
        <p className="muted">{t("customerPortal.placeholder")}</p>
      </section>
    </div>
  );
}
