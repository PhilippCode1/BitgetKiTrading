/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import {
  actionDisabledReason,
  ExecutionSafetyPanel,
} from "@/components/safety/ExecutionSafetyPanel";

jest.mock("next/navigation", () => ({
  usePathname: () => "/console/live-broker",
  useRouter: () => ({
    refresh: jest.fn(),
    replace: jest.fn(),
    push: jest.fn(),
  }),
}));

function renderDe(ui: ReactElement) {
  return render(<I18nProvider initialLocale="de">{ui}</I18nProvider>);
}

describe("ExecutionSafetyPanel", () => {
  it("zeigt deaktivierten Zustand ohne Endpoint", () => {
    renderDe(
      <ExecutionSafetyPanel
        killSwitchActive={false}
        safetyLatchActive={false}
        reconcileOk={true}
      />,
    );
    const arm = screen.getByRole("button", {
      name: /Kill-Switch armieren/i,
    });
    expect(arm).toBeEnabled();
    expect(
      screen.getAllByText(/Endpoint fehlt, Aktion ist sicher deaktiviert/i)
        .length,
    ).toBeGreaterThan(0);
  });

  it("zeigt Bestätigungsbereich für Notfallaktion", () => {
    renderDe(
      <ExecutionSafetyPanel
        killSwitchActive={false}
        safetyLatchActive={false}
        reconcileOk={true}
      />,
    );
    const btn = screen.getByRole("button", { name: /Emergency-Flatten/i });
    fireEvent.click(btn);
    expect(
      screen.getByRole("button", { name: /Ausführen \(deaktiviert/i }),
    ).toBeDisabled();
  });

  it("blockiert normale Aktionen bei Safety-Latch oder Kill-Switch", () => {
    const baseAction = {
      id: "cancel_all" as const,
      titleKey: "console.executionSafetyPanel.cancelAll",
      dangerous: true,
      endpoint: "/x",
      endpointAvailable: true,
    };
    const t = (key: string) => key;
    expect(
      actionDisabledReason({
        action: baseAction,
        killSwitchActive: true,
        safetyLatchActive: false,
        reconcileOk: true,
        t,
      }),
    ).toBe("console.executionSafetyPanel.reasonKillSwitch");
    expect(
      actionDisabledReason({
        action: baseAction,
        killSwitchActive: false,
        safetyLatchActive: true,
        reconcileOk: true,
        t,
      }),
    ).toBe("console.executionSafetyPanel.reasonSafetyLatch");
  });
});
