import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function CustomerBillingPage() {
  const t = await getServerTranslator();
  return (
    <div className="panel">
      <h1 style={{ marginTop: 0 }}>{t("customerPortal.nav.billing")}</h1>
      <p className="muted">{t("customerPortal.placeholder")}</p>
    </div>
  );
}
