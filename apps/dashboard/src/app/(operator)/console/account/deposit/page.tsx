import { Header } from "@/components/layout/Header";
import { DepositCheckoutPanel } from "@/components/account/DepositCheckoutPanel";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function AccountDepositPage() {
  const t = await getServerTranslator();
  return (
    <>
      <Header
        title={t("account.deposit.title")}
        subtitle={t("account.deposit.subtitle")}
      />
      <DepositCheckoutPanel />
    </>
  );
}
