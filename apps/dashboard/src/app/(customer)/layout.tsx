import type { Metadata } from "next";
import type { ReactNode } from "react";

import { CustomerShell } from "@/components/layout/CustomerShell";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getServerTranslator();
  return {
    title: t("customerPortal.metaTitle"),
    description: t("customerPortal.overviewLead"),
  };
}

type Props = Readonly<{ children: ReactNode }>;

/**
 * Endkunden-Route-Group (Modul Mate): abgeschottet von (operator)/console.
 * Autorisierung: Mandanten-JWT im Cookie `bitget_portal_jwt` (siehe middleware).
 */
export default async function CustomerPortalLayout({ children }: Props) {
  return <CustomerShell>{children}</CustomerShell>;
}
