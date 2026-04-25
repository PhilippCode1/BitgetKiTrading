/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, screen, within } from "@testing-library/react";
import type { ReactElement } from "react";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { SidebarNav } from "@/components/layout/SidebarNav";

jest.mock("next/navigation", () => ({
  usePathname: () => "/console/ops",
  useRouter: () => ({
    refresh: jest.fn(),
    replace: jest.fn(),
    push: jest.fn(),
  }),
}));

function renderNav(ui: ReactElement) {
  return render(<I18nProvider initialLocale="en">{ui}</I18nProvider>);
}

describe("SidebarNav", () => {
  it("blendet Admin-Link ohne Berechtigung aus", () => {
    renderNav(<SidebarNav showAdminNav={false} />);
    expect(screen.queryByRole("link", { name: /Admin cockpit/i })).toBeNull();
    expect(
      screen.getByRole("link", { name: /Operator Cockpit/i }),
    ).toBeInTheDocument();
  });

  it("zeigt Admin-Link bei serverseitig freigegebener Admin-Navigation", () => {
    renderNav(<SidebarNav showAdminNav />);
    expect(
      screen.getByRole("link", { name: /Admin cockpit/i }),
    ).toBeInTheDocument();
  });

  it("Pro: Health sitzt beim Cockpit; Integration-Check unter Transparenz", () => {
    renderNav(<SidebarNav showAdminNav={false} />);
    const cockpitHeading = screen.getByText("Cockpit, approvals & system");
    const cockpitNav = cockpitHeading.nextElementSibling;
    expect(cockpitNav?.tagName.toLowerCase()).toBe("nav");
    expect(
      within(cockpitNav as HTMLElement).getByRole("link", {
        name: /Health & incidents/i,
      }),
    ).toBeInTheDocument();

    const opsHeading = screen.getByText("News, plan & integrations");
    const opsNav = opsHeading.nextElementSibling;
    expect(
      within(opsNav as HTMLElement).getByRole("link", {
        name: /Integration check/i,
      }),
    ).toBeInTheDocument();
    expect(
      within(opsNav as HTMLElement).queryByRole("link", {
        name: /Health & incidents/i,
      }),
    ).toBeNull();
  });

  it("Simple-Ansicht: Schnellzugriff mit KI, Paper, Konto; Hilfe prominent; kein Operator Cockpit", () => {
    renderNav(<SidebarNav showAdminNav={false} uiMode="simple" />);
    expect(screen.getByRole("link", { name: /^Home$/i })).toBeInTheDocument();
    const quickHeading = screen.getByText("Quick access");
    const quickNav = quickHeading.nextElementSibling;
    expect(quickNav?.tagName.toLowerCase()).toBe("nav");
    expect(
      within(quickNav as HTMLElement).getByRole("link", {
        name: /AI & system status/i,
      }),
    ).toBeInTheDocument();
    expect(
      within(quickNav as HTMLElement).getByRole("link", {
        name: /Central diagnostics/i,
      }),
    ).toBeInTheDocument();
    expect(
      within(quickNav as HTMLElement).getByRole("link", {
        name: /Practice \(paper\)/i,
      }),
    ).toBeInTheDocument();
    expect(
      within(quickNav as HTMLElement).getByRole("link", {
        name: /^My account$/i,
      }),
    ).toBeInTheDocument();

    const helpLink = screen.getByRole("link", { name: /Help & overview/i });
    expect(helpLink).toHaveAttribute("href", "/console/help");
    expect(
      screen.getByRole("link", { name: /Chart & market/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /Operator Cockpit/i }),
    ).toBeNull();
    expect(screen.queryByRole("link", { name: /No-trade/i })).toBeNull();
  });
});
