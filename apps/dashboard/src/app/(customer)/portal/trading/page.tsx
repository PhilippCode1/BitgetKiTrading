import { getCustomerPortalSummary } from "@/lib/customer-portal-summary";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function CustomerPortalTradingReadonlyPage() {
  const t = await getServerTranslator();
  const s = await getCustomerPortalSummary();

  return (
    <div className="panel" data-e2e="customer-portal-trading">
      <h1 style={{ marginTop: 0 }}>{t("customerPortal.tradingPage.title")}</h1>
      <p className="muted">{t("customerPortal.tradingPage.lead")}</p>
      <p className="muted" style={{ marginTop: 12 }}>
        {t("customerPortal.tradingPage.bffState")} <code>{s.tradingReadonly.dataState}</code> /{" "}
        <code>{s.tradingReadonly.code}</code>
      </p>
      <p className="muted" style={{ fontSize: "0.95rem" }}>
        {t("customerPortal.tradingPage.noExecution")}
      </p>
    </div>
  );
}
