"use client";

import { useI18n } from "@/components/i18n/I18nProvider";
import type { LiveFeatureSnapshot } from "@/lib/types";

type Props = {
  feature: LiveFeatureSnapshot | null | undefined;
};

function fmt(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

function fmtAge(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  if (value < 1000) return `${Math.round(value)} ms`;
  return `${(value / 1000).toFixed(1)} s`;
}

export function MicrostructurePanel({ feature }: Props) {
  const { t } = useI18n();
  if (!feature) {
    return (
      <div className="panel">
        <h2>{t("pages.terminal.microTitle")}</h2>
        <p className="muted">{t("pages.terminal.microEmpty")}</p>
      </div>
    );
  }
  return (
    <div className="panel">
      <h2>{t("pages.terminal.microTitle")}</h2>
      <div className="signal-grid">
        <div>
          <span className="label">{t("pages.terminal.microSpread")}</span>
          <strong>{fmt(feature.spread_bps)} bps</strong>
        </div>
        <div>
          <span className="label">{t("pages.terminal.microExecCost")}</span>
          <strong>{fmt(feature.execution_cost_bps)} bps</strong>
        </div>
        <div>
          <span className="label">{t("pages.terminal.microVolCost")}</span>
          <strong>{fmt(feature.volatility_cost_bps)} bps</strong>
        </div>
        <div>
          <span className="label">{t("pages.terminal.microFunding")}</span>
          <strong>{fmt(feature.funding_rate_bps)} bps</strong>
        </div>
        <div>
          <span className="label">{t("pages.terminal.microOiDelta")}</span>
          <strong>{fmt(feature.open_interest_change_pct)}%</strong>
        </div>
        <div>
          <span className="label">{t("pages.terminal.microDepthVol")}</span>
          <strong>{fmt(feature.depth_to_bar_volume_ratio)}</strong>
        </div>
      </div>
      <section className="mt">
        <h3>{t("pages.terminal.microSources")}</h3>
        <ul className="warnings">
          <li>
            {t("pages.terminal.microSourceLine", {
              label: t("pages.terminal.microLiq"),
              source: feature.liquidity_source ?? "—",
              age: fmtAge(feature.orderbook_age_ms),
            })}
          </li>
          <li>
            {t("pages.terminal.microSourceLine", {
              label: t("pages.terminal.microFund"),
              source: feature.funding_source ?? "—",
              age: fmtAge(feature.funding_age_ms),
            })}
          </li>
          <li>
            {t("pages.terminal.microSourceLine", {
              label: t("pages.terminal.microOi"),
              source: feature.open_interest_source ?? "—",
              age: fmtAge(feature.open_interest_age_ms),
            })}
          </li>
        </ul>
      </section>
    </div>
  );
}
