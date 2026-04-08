import { Header } from "@/components/layout/Header";
import { DiagnosticsCenterClient } from "@/components/diagnostics/DiagnosticsCenterClient";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function DiagnosticsCenterPage() {
  const t = await getServerTranslator();
  return (
    <>
      <Header
        title={t("pages.diagnostics.title")}
        subtitle={t("pages.diagnostics.subtitle")}
        helpBriefKey="pages.diagnostics.helpBrief"
        helpDetailKey="pages.diagnostics.helpDetail"
      />
      <DiagnosticsCenterClient />
    </>
  );
}
