/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

import { MarketCapabilityMatrixTable } from "@/components/market/MarketCapabilityMatrixTable";
import type { MarketUniverseCategoryRow } from "@/lib/types";

const baseRow = (): MarketUniverseCategoryRow => ({
  schema_version: "v1",
  venue: "bitget",
  market_family: "futures",
  product_type: "usdt-m",
  margin_account_mode: "cross",
  category_key: "futures_usdt_m",
  metadata_source: "fixture",
  metadata_verified: true,
  inventory_visible: true,
  analytics_eligible: true,
  paper_shadow_eligible: true,
  live_execution_enabled: false,
  execution_disabled: true,
  supports_funding: true,
  supports_open_interest: true,
  supports_long_short: true,
  supports_shorting: true,
  supports_reduce_only: true,
  supports_leverage: true,
  uses_spot_public_market_data: false,
  instrument_count: 120,
  tradeable_instrument_count: 100,
  subscribable_instrument_count: 110,
  metadata_verified_count: 90,
  sample_symbols: ["BTCUSDT", "ETHUSDT"],
  reasons: [],
});

describe("MarketCapabilityMatrixTable", () => {
  it("rendert Kategorie-Key und Capability-Spalten fuer Futures", () => {
    render(<MarketCapabilityMatrixTable categories={[baseRow()]} />);
    expect(screen.getByText("futures_usdt_m")).toBeInTheDocument();
    expect(screen.getByText(/futures \/ usdt-m/i)).toBeInTheDocument();
    expect(screen.getByText("120 / tradeable 100")).toBeInTheDocument();
    expect(screen.getByText("BTCUSDT, ETHUSDT")).toBeInTheDocument();
  });

  it("labelt Margin-Kategorien mit account mode", () => {
    const row = baseRow();
    row.market_family = "margin";
    row.margin_account_mode = "isolated";
    row.category_key = "margin_iso";
    render(<MarketCapabilityMatrixTable categories={[row]} />);
    expect(screen.getByText(/margin \/ isolated/i)).toBeInTheDocument();
  });

  it("nutzt market_family direkt fuer Spot/sonstige Familien", () => {
    const row = baseRow();
    row.market_family = "spot";
    row.category_key = "spot_usdt";
    render(<MarketCapabilityMatrixTable categories={[row]} />);
    expect(screen.getByText("spot")).toBeInTheDocument();
  });
});
