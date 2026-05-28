import type { Metadata } from "next";
import type { ReactNode } from "react";

import { FlowNavBar } from "@/components/layout/FlowNavBar";
import { getServerTranslator } from "@/lib/i18n/server-translate";

/** Sprach-Gate ohne Marketing-Shell — nur Schritt 1. */
export const metadata: Metadata = {
  title: "Sprache / Language",
  robots: { index: false, follow: false },
};

export default async function WelcomeLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  const t = await getServerTranslator();
  return (
    <>
      <a href="#dash-main-content" className="skip-to-main">
        {t("ui.skipToMain")}
      </a>
      <FlowNavBar />
      <div id="dash-main-content">{children}</div>
    </>
  );
}
