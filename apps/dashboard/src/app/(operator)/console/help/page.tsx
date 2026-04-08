import Link from "next/link";

import { Header } from "@/components/layout/Header";
import { ContentPanel } from "@/components/ui/ContentPanel";
import { ONBOARDING_NAV_HREF } from "@/lib/onboarding-flow";
import { CONSOLE_BASE, consolePath } from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function ConsoleHelpHubPage() {
  const t = await getServerTranslator();
  const links: { href: string; labelKey: string }[] = [
    { href: consolePath("terminal"), labelKey: "pages.consoleHelp.linkChart" },
    { href: consolePath("signals"), labelKey: "pages.consoleHelp.linkSignals" },
    { href: consolePath("health"), labelKey: "pages.consoleHelp.linkHealth" },
    { href: consolePath("paper"), labelKey: "pages.consoleHelp.linkPaper" },
    { href: consolePath("account"), labelKey: "pages.consoleHelp.linkAccount" },
    {
      href: `${CONSOLE_BASE}/account/language`,
      labelKey: "pages.consoleHelp.linkSettings",
    },
    { href: ONBOARDING_NAV_HREF, labelKey: "pages.consoleHelp.linkOnboarding" },
    { href: CONSOLE_BASE, labelKey: "pages.consoleHelp.linkHome" },
  ];
  return (
    <>
      <Header
        title={t("pages.consoleHelp.title")}
        subtitle={t("pages.consoleHelp.subtitle")}
        helpBriefKey="help.consoleHelpHub.brief"
        helpDetailKey="help.consoleHelpHub.detail"
      />
      <ContentPanel>
        <p className="muted small" style={{ marginBottom: 16 }}>
          {t("pages.consoleHelp.intro")}
        </p>
        <ul className="console-help-hub-list">
          {links.map((item) => (
            <li key={item.href}>
              <Link href={item.href} className="console-help-hub-link">
                {t(item.labelKey)}
              </Link>
            </li>
          ))}
        </ul>
      </ContentPanel>
    </>
  );
}
