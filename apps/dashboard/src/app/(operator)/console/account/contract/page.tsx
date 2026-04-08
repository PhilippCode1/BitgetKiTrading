import { Header } from "@/components/layout/Header";
import { ContractWorkflowClient } from "@/components/account/ContractWorkflowClient";
import {
  fetchCommerceContractTemplates,
  fetchCommerceCustomerContracts,
} from "@/lib/api";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function AccountContractPage() {
  const t = await getServerTranslator();
  let templates: Record<string, unknown>[] = [];
  let contracts: Record<string, unknown>[] = [];
  let err: string | null = null;
  try {
    const [a, b] = await Promise.all([
      fetchCommerceContractTemplates(),
      fetchCommerceCustomerContracts(),
    ]);
    templates = (a.templates as Record<string, unknown>[] | undefined) ?? [];
    contracts = (b.contracts as Record<string, unknown>[] | undefined) ?? [];
  } catch (e) {
    err = e instanceof Error ? e.message : t("account.contract.loadErr");
  }

  return (
    <>
      <Header
        title={t("account.contract.title")}
        subtitle={t("account.contract.subtitle")}
        helpBriefKey="help.usage.brief"
        helpDetailKey="help.usage.detail"
      />
      <ContractWorkflowClient
        initialTemplates={templates}
        initialContracts={contracts}
        loadError={err}
      />
    </>
  );
}
