import type { ReactNode } from "react";

import { HelpHint } from "@/components/help/HelpHint";
import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import { ConsoleBreadcrumbs } from "@/components/layout/ConsoleBreadcrumbs";
import { SidebarNav } from "@/components/layout/SidebarNav";
import { UiModeSwitcher } from "@/components/layout/UiModeSwitcher";
import type { UiMode } from "@/lib/dashboard-prefs";

type Props = Readonly<{
  children: ReactNode;
  showAdminNav: boolean;
  uiMode: UiMode;
  /** Optional: z. B. Gateway-Heartbeat — ruhiger Verbindungsindikator */
  topBarExtra?: ReactNode;
}>;

export function DashboardShell({
  children,
  showAdminNav,
  uiMode,
  topBarExtra,
}: Props) {
  return (
    <div className="dash-shell">
      <SidebarNav showAdminNav={showAdminNav} uiMode={uiMode} />
      <div className="dash-main-wrap">
        <div className="dash-locale-bar">
          <div className="dash-bar-group">
            <UiModeSwitcher initialMode={uiMode} />
            <HelpHint briefKey="help.mode.brief" detailKey="help.mode.detail" />
          </div>
          <div className="dash-bar-group">
            <LocaleSwitcher />
            <HelpHint
              briefKey="help.language.brief"
              detailKey="help.language.detail"
            />
          </div>
          {topBarExtra ? (
            <div className="dash-bar-group dash-bar-group--heartbeat">
              {topBarExtra}
            </div>
          ) : null}
        </div>
        <main className="dash-main">
          <ConsoleBreadcrumbs />
          {children}
        </main>
      </div>
    </div>
  );
}
