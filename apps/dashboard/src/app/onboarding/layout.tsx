import type { Metadata } from "next";
import type { ReactNode } from "react";

import { FlowNavBar } from "@/components/layout/FlowNavBar";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getServerTranslator();
  return {
    title: t("onboarding.metaTitle"),
    description: t("onboarding.metaDescription"),
    robots: { index: false, follow: false },
  };
}

export default async function OnboardingLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <>
      <FlowNavBar />
      {children}
    </>
  );
}
