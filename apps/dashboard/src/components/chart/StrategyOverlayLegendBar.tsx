"use client";

import type {
  StrategyOverlayModel,
  StrategyOverlayLayerId,
} from "@/lib/chart/strategy-overlay-model";
import { STRATEGY_OVERLAY_LAYERS } from "@/lib/chart/strategy-overlay-model";
import { useI18n } from "@/components/i18n/I18nProvider";

type Props = Readonly<{
  model: StrategyOverlayModel | null;
  masterEnabled: boolean;
  onMasterChange: (v: boolean) => void;
  layerVisible: Readonly<Record<StrategyOverlayLayerId, boolean>>;
  onLayerChange: (id: StrategyOverlayLayerId, v: boolean) => void;
}>;

export function StrategyOverlayLegendBar({
  model,
  masterEnabled,
  onMasterChange,
  layerVisible,
  onLayerChange,
}: Props) {
  const { t } = useI18n();

  if (!model) {
    return null;
  }

  const hasLines = model.lines.length > 0;
  const hasMeta = Boolean(model.regimeText || model.invalidationText);

  if (!hasLines && !hasMeta) {
    return null;
  }

  const lineIdsPresent = new Set(model.lines.map((l) => l.id));

  return (
    <div
      className="strategy-overlay-legend"
      role="group"
      aria-label={t("ui.chart.strategy.legendAria")}
    >
      <div className="strategy-overlay-legend__row strategy-overlay-legend__row--master">
        <label className="strategy-overlay-legend__check">
          <input
            type="checkbox"
            checked={masterEnabled}
            onChange={(e) => onMasterChange(e.target.checked)}
          />
          <span title={t("ui.chart.strategy.masterHint")}>
            {t("ui.chart.strategy.masterLabel")}
          </span>
        </label>
      </div>
      {masterEnabled && hasLines ? (
        <div className="strategy-overlay-legend__row strategy-overlay-legend__layers">
          {STRATEGY_OVERLAY_LAYERS.map((id) => {
            if (!lineIdsPresent.has(id)) return null;
            return (
              <label key={id} className="strategy-overlay-legend__check">
                <input
                  type="checkbox"
                  checked={layerVisible[id] !== false}
                  onChange={(e) => onLayerChange(id, e.target.checked)}
                />
                <span title={t(`ui.chart.strategy.layerHint.${id}`)}>
                  {t(`ui.chart.strategy.layer.${id}`)}
                </span>
              </label>
            );
          })}
        </div>
      ) : null}
      {model.regimeText ? (
        <p
          className="muted small strategy-overlay-legend__meta"
          title={t("ui.chart.strategy.regimeHint")}
        >
          <strong>{t("ui.chart.strategy.regimeLabel")}</strong>{" "}
          {model.regimeText}
        </p>
      ) : null}
      {model.invalidationText ? (
        <p
          className="muted small strategy-overlay-legend__meta"
          title={t("ui.chart.strategy.invalidationHint")}
        >
          <strong>{t("ui.chart.strategy.invalidationLabel")}</strong>{" "}
          {model.invalidationText}
        </p>
      ) : null}
    </div>
  );
}
