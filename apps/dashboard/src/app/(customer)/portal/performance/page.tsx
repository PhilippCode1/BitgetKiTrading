import { CustomerPerformanceTable } from "@/components/portal/CustomerPerformanceTable";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function CustomerPerformancePage() {
  const t = await getServerTranslator();
  return (
    <div className="panel">
      <h1 style={{ marginTop: 0 }}>{t("customerPortal.performancePage.title")}</h1>
      <p className="muted">{t("customerPortal.performancePage.lead")}</p>
      <CustomerPerformanceTable />
    </div>
  );
}
