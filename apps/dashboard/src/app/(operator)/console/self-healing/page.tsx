import { Suspense } from "react";

import { Header } from "@/components/layout/Header";
import { SelfHealingHubClient } from "@/components/self-healing/SelfHealingHubClient";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function SelfHealingPage() {
  const t = await getServerTranslator();
  return (
    <>
      <Header
        title={t("pages.selfHealing.title")}
        subtitle={t("pages.selfHealing.subtitle")}
        helpBriefKey="help.selfHealingPage.brief"
        helpDetailKey="help.selfHealingPage.detail"
      />
      <Suspense
        fallback={
          <p className="muted small panel">{t("pages.selfHealing.loading")}</p>
        }
      >
        <SelfHealingHubClient />
      </Suspense>
    </>
  );
}
