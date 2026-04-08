import { CustomerProfileForm } from "@/components/account/CustomerProfileForm";
import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { Header } from "@/components/layout/Header";
import { fetchCommerceCustomerMe } from "@/lib/api";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function AccountProfilePage() {
  const t = await getServerTranslator();
  let profile: Record<string, unknown> | null = null;
  let err: string | null = null;
  try {
    const me = await fetchCommerceCustomerMe();
    profile = (me.profile as Record<string, unknown> | undefined) ?? null;
  } catch (e) {
    err = e instanceof Error ? e.message : t("account.loadError");
  }

  const display =
    profile?.display_name != null && profile.display_name !== ""
      ? String(profile.display_name)
      : null;

  return (
    <>
      <Header
        title={t("account.profile.title")}
        subtitle={t("account.profile.subtitle")}
      />
      {err ? (
        <PanelDataIssue err={err} diagnostic={false} t={t} />
      ) : (
        <CustomerProfileForm initialDisplayName={display} />
      )}
    </>
  );
}
