import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function CustomerPortalHomePage() {
  const t = await getServerTranslator();
  return (
    <div className="panel">
      <h1 style={{ marginTop: 0 }}>{t("customerPortal.overviewTitle")}</h1>
      <p className="muted">{t("customerPortal.overviewLead")}</p>
    </div>
  );
}
