/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";

import {
  actionDisabledReason,
  ExecutionSafetyPanel,
} from "@/components/safety/ExecutionSafetyPanel";

describe("ExecutionSafetyPanel", () => {
  it("zeigt deaktivierten Zustand ohne Endpoint", () => {
    render(
      <ExecutionSafetyPanel
        killSwitchActive={false}
        safetyLatchActive={false}
        reconcileOk={true}
      />,
    );
    const arm = screen.getByRole("button", { name: /Kill-Switch armieren pruefen/i });
    expect(arm).toBeEnabled();
    expect(
      screen.getAllByText(/Endpoint fehlt, Aktion ist sicher deaktiviert./i).length,
    ).toBeGreaterThan(0);
  });

  it("zeigt Bestaetigungsdialog fuer Notfallaktion", () => {
    render(
      <ExecutionSafetyPanel
        killSwitchActive={false}
        safetyLatchActive={false}
        reconcileOk={true}
      />,
    );
    const btn = screen.getByRole("button", { name: /Emergency-Flatten/i });
    fireEvent.click(btn);
    expect(screen.getByRole("dialog", { name: /Bestaetigung fuer Sicherheitsaktion/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Aktion ausfuehren \(derzeit deaktiviert\)/i }),
    ).toBeDisabled();
  });

  it("blockiert normale Aktionen bei Safety-Latch oder Kill-Switch", () => {
    const baseAction = {
      id: "cancel_all",
      title: "Cancel-All",
      dangerous: true,
      endpoint: "/x",
      endpointAvailable: true,
    } as const;
    expect(
      actionDisabledReason({
        action: baseAction,
        killSwitchActive: true,
        safetyLatchActive: false,
        reconcileOk: true,
      }),
    ).toMatch(/Kill-Switch aktiv/i);
    expect(
      actionDisabledReason({
        action: baseAction,
        killSwitchActive: false,
        safetyLatchActive: true,
        reconcileOk: true,
      }),
    ).toMatch(/Safety-Latch aktiv/i);
  });
});
