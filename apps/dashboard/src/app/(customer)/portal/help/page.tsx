import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function CustomerHelpPage() {
  const t = await getServerTranslator();
  return (
    <div className="panel">
      <h1 style={{ marginTop: 0 }}>{t("customerPortal.help.title")}</h1>
      <p className="muted">{t("customerPortal.help.lead")}</p>
    </div>
  );
}
