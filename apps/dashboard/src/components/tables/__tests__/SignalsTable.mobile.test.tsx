/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, within } from "@testing-library/react";
import type { ReactElement } from "react";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { SignalsTable } from "@/components/tables/SignalsTable";
import type { SignalRecentItem } from "@/lib/types";

jest.mock("next/navigation", () => ({
  usePathname: () => "/console/signals",
  useRouter: () => ({
    refresh: jest.fn(),
    replace: jest.fn(),
    push: jest.fn(),
  }),
}));

function wrap(ui: ReactElement) {
  return render(<I18nProvider initialLocale="de">{ui}</I18nProvider>);
}

const minimalSignal: SignalRecentItem = {
  signal_id: "sig-test-1",
  symbol: "BTCUSDT",
  timeframe: "5m",
  direction: "long",
  signal_class: "standard",
  decision_state: "released",
  signal_strength_0_100: 50,
  probability_0_1: 0.5,
  analysis_ts_ms: 1_700_000_000_000,
  created_ts: null,
  outcome_badge: null,
  trade_action: "allow_trade",
  governor_universal_hard_block_reasons_json: [],
  live_execution_block_reasons_json: [],
  live_execution_clear_for_real_money: true,
};

describe("SignalsTable — mobile Karten im DOM", () => {
  it("rendert Kartenliste und Desktop-Tabelle parallel", () => {
    const { container } = wrap(<SignalsTable items={[minimalSignal]} />);
    const cards = container.querySelector(".signals-mobile-cards");
    expect(cards).toBeTruthy();
    expect(
      within(cards as HTMLElement).getByText("BTCUSDT"),
    ).toBeInTheDocument();
    expect(container.querySelector("table.data-table")).toBeTruthy();
  });
});
