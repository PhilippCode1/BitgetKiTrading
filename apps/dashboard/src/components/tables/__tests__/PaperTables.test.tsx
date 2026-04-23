/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, screen, within } from "@testing-library/react";
import type { ReactElement } from "react";

import { I18nProvider } from "@/components/i18n/I18nProvider";

import { OpenPositionsTable } from "../OpenPositionsTable";
import { TradesTable } from "../TradesTable";

jest.mock("next/navigation", () => ({
  usePathname: () => "/console/paper",
  useRouter: () => ({
    refresh: jest.fn(),
    replace: jest.fn(),
    push: jest.fn(),
  }),
}));

function wrap(ui: ReactElement) {
  return render(<I18nProvider initialLocale="de">{ui}</I18nProvider>);
}

describe("Paper-Tabellen (i18n)", () => {
  it("OpenPositionsTable: Leerzustand auf Deutsch", () => {
    wrap(<OpenPositionsTable positions={[]} />);
    expect(screen.getByText("Keine offenen Positionen")).toBeInTheDocument();
  });

  it("TradesTable: Leerzustand auf Deutsch", () => {
    wrap(<TradesTable trades={[]} />);
    expect(
      screen.getByText("Noch keine geschlossenen Trades"),
    ).toBeInTheDocument();
  });

  it("OpenPositionsTable: Skeleton während isLoading", () => {
    wrap(<OpenPositionsTable isLoading positions={[]} />);
    expect(
      screen.getByRole("status", { name: "Tabelle wird geladen" }),
    ).toBeInTheDocument();
  });

  it("OpenPositionsTable: Mobile-Kartenliste bei Daten", () => {
    const { container } = wrap(
      <OpenPositionsTable
        positions={[
          {
            position_id: "p1",
            symbol: "ETHUSDT",
            side: "long",
            qty_base: "0.1",
            entry_price_avg: "2000",
            leverage: "5",
            mark_price: 2010,
            unrealized_pnl_usdt: 1.2,
            opened_ts_ms: 1_700_000_000_000,
            meta: {},
          },
        ]}
      />,
    );
    const list = container.querySelector(
      ".console-stack-list.console-mobile-only",
    );
    expect(list).toBeTruthy();
    expect(
      within(list as HTMLElement).getByText("ETHUSDT"),
    ).toBeInTheDocument();
  });
});
