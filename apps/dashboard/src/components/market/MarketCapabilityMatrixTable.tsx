"use client";

import { useMemo } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import type { MarketUniverseCategoryRow } from "@/lib/types";

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
  const { t } = useI18n();

  const boolLabel = useMemo(
    () => (value: boolean) =>
      value ? t("pages.ops.valueYes") : t("pages.ops.valueNo"),
    [t],
  );

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>{t("pages.capabilities.matrixThCategory")}</th>
            <th>{t("pages.capabilities.matrixThCategoryKey")}</th>
            <th>{t("pages.capabilities.matrixThInventory")}</th>
            <th>{t("pages.capabilities.matrixThAnalytics")}</th>
            <th>{t("pages.capabilities.matrixThPaperShadow")}</th>
            <th>{t("pages.capabilities.matrixThLive")}</th>
            <th>{t("pages.capabilities.matrixThExecDisabled")}</th>
            <th>{t("pages.capabilities.matrixThLeverage")}</th>
            <th>{t("pages.capabilities.matrixThShorting")}</th>
            <th>{t("pages.capabilities.matrixThFundingOi")}</th>
            <th>{t("pages.capabilities.matrixThInstruments")}</th>
            <th>{t("pages.capabilities.matrixThSamples")}</th>
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
                {t("pages.capabilities.matrixInstrumentCount", {
                  count: item.instrument_count,
                  tradeable: item.tradeable_instrument_count,
                })}
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
