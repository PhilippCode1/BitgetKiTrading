import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function CustomerPortalRiskPage() {
  const t = await getServerTranslator();
  return (
    <div className="panel" data-e2e="customer-portal-risk">
      <h1 style={{ marginTop: 0 }}>{t("customerPortal.riskPage.title")}</h1>
      <p className="muted">{t("customerPortal.riskPage.lead")}</p>
      <ol className="muted" style={{ lineHeight: 1.65, paddingLeft: "1.2rem" }}>
        <li>{t("customerPortal.riskPage.point1")}</li>
        <li>{t("customerPortal.riskPage.point2")}</li>
        <li>{t("customerPortal.riskPage.point3")}</li>
        <li>{t("customerPortal.riskPage.point4")}</li>
      </ol>
      <p className="muted" style={{ marginTop: 20, fontSize: "0.95rem" }}>
        {t("customerPortal.riskPage.ackProcess")}
      </p>
    </div>
  );
}
