import type { MarketUniverseCategoryRow } from "@/lib/types";

function boolLabel(value: boolean): string {
  return value ? "ja" : "nein";
}

function categoryLabel(item: MarketUniverseCategoryRow): string {
  if (item.market_family === "futures") {
    return `${item.market_family} / ${item.product_type ?? "—"}`;
  }
  if (item.market_family === "margin") {
    return `${item.market_family} / ${item.margin_account_mode}`;
  }
  return item.market_family;
}

type Props = Readonly<{
  categories: readonly MarketUniverseCategoryRow[];
}>;

export function MarketCapabilityMatrixTable({ categories }: Props) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Kategorie</th>
            <th>Category Key</th>
            <th>Inventar</th>
            <th>Analytics</th>
            <th>Paper/Shadow</th>
            <th>Live</th>
            <th>Exec disabled</th>
            <th>Leverage</th>
            <th>Shorting</th>
            <th>Funding/OI</th>
            <th>Instrumente</th>
            <th>Samples</th>
          </tr>
        </thead>
        <tbody>
          {categories.map((item) => (
            <tr key={item.category_key}>
              <td>{categoryLabel(item)}</td>
              <td className="mono-small">{item.category_key}</td>
              <td>{boolLabel(item.inventory_visible)}</td>
              <td>{boolLabel(item.analytics_eligible)}</td>
              <td>{boolLabel(item.paper_shadow_eligible)}</td>
              <td>{boolLabel(item.live_execution_enabled)}</td>
              <td>{boolLabel(item.execution_disabled)}</td>
              <td>{boolLabel(item.supports_leverage)}</td>
              <td>{boolLabel(item.supports_shorting)}</td>
              <td>
                {boolLabel(item.supports_funding)} /{" "}
                {boolLabel(item.supports_open_interest)}
              </td>
              <td>
                {item.instrument_count} / tradeable{" "}
                {item.tradeable_instrument_count}
              </td>
              <td className="mono-small">
                {item.sample_symbols.join(", ") || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
