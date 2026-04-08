import Link from "next/link";

import { Header } from "@/components/layout/Header";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function AccountLanguagePage() {
  const t = await getServerTranslator();
  return (
    <>
      <Header
        title={t("account.language.title")}
        subtitle={t("account.language.subtitle")}
        helpBriefKey="help.language.brief"
        helpDetailKey="help.language.detail"
      />
      <p className="muted">{t("account.language.body")}</p>
      <p className="muted small">
        <Link href="/welcome?returnTo=%2Fconsole%2Faccount%2Flanguage">
          {t("welcome.title")}
        </Link>
      </p>
    </>
  );
}
