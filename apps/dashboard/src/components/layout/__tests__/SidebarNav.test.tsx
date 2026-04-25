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
    expect(screen.getByRole("link", { name: /^Risk$/i })).toBeInTheDocument();
  });

  it("zeigt auch mit Admin-Berechtigung nur Main-Console-Module", () => {
    renderNav(<SidebarNav showAdminNav />);
    expect(screen.queryByRole("link", { name: /Admin cockpit/i })).toBeNull();
    expect(screen.getByRole("link", { name: /^Settings$/i })).toBeInTheDocument();
  });

  it("Pro: zentrale Main-Console-Navigation ohne Legacy-Integrationslink", () => {
    renderNav(<SidebarNav showAdminNav={false} />);
    const mainConsoleHeading = screen.getByText("Main Console");
    const mainConsoleNav = mainConsoleHeading.nextElementSibling;
    expect(mainConsoleNav?.tagName.toLowerCase()).toBe("nav");
    expect(
      within(mainConsoleNav as HTMLElement).getByRole("link", {
        name: /^System$/i,
      }),
    ).toBeInTheDocument();
    expect(
      within(mainConsoleNav as HTMLElement).queryByRole("link", {
        name: /Integration check/i,
      }),
    ).toBeNull();
    const expectedModules = [
      "Overview",
      "Assets",
      "Charts",
      "Signals",
      "Risk",
      "Broker",
      "Safety",
      "System",
      "Reports",
      "Settings",
    ];
    for (const moduleName of expectedModules) {
      expect(
        within(mainConsoleNav as HTMLElement).getByRole("link", {
          name: new RegExp(`^${moduleName}$`, "i"),
        }),
      ).toBeInTheDocument();
    }
    const forbidden = ["Billing", "Customer", "Pricing", "Tenant", "Contract"];
    for (const word of forbidden) {
      expect(
        within(mainConsoleNav as HTMLElement).queryByRole("link", {
          name: new RegExp(word, "i"),
        }),
      ).toBeNull();
    }
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
