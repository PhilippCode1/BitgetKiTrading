import { Header } from "@/components/layout/Header";
import { TelegramAccountPanel } from "@/components/account/TelegramAccountPanel";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function AccountTelegramPage() {
  const t = await getServerTranslator();
  return (
    <>
      <Header
        title={t("account.telegram.title")}
        subtitle={t("account.telegram.subtitle")}
        helpBriefKey="help.telegram.brief"
        helpDetailKey="help.telegram.detail"
      />
      <TelegramAccountPanel />
    </>
  );
}
