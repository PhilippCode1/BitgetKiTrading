import type { Metadata } from "next";
import type { ReactNode } from "react";
import { DM_Sans } from "next/font/google";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { getRequestLocale } from "@/lib/i18n/server";
import { getMessagesForLocale } from "@/lib/i18n/load-messages";
import { buildTranslator } from "@/lib/i18n/resolve-message";

import "./globals.css";

const fontUi = DM_Sans({
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-ui",
  display: "swap",
});

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getRequestLocale();
  const { messages, fallback } = getMessagesForLocale(locale);
  const t = buildTranslator(locale, messages, fallback);
  return {
    title: t("public.metaTitle"),
    description: t("public.metaDescription"),
  };
}

type RootLayoutProps = Readonly<{
  children: ReactNode;
}>;

export default async function RootLayout({ children }: RootLayoutProps) {
  const locale = await getRequestLocale();
  return (
    <html lang={locale} className={fontUi.variable}>
      <body>
        <I18nProvider initialLocale={locale}>{children}</I18nProvider>
      </body>
    </html>
  );
}
