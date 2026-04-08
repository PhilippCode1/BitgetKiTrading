"use client";

import { useEffect, useMemo, useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import type { LiveDataSurfaceModel } from "@/lib/live-data-surface-model";
import {
  liveDataSurfaceToCommsPhase,
  liveDataSurfaceToExpectation,
} from "@/lib/system-communication";

function ageSeconds(ts: number | null, nowMs: number): number | null {
  if (ts == null || !Number.isFinite(ts)) return null;
  const s = Math.floor((nowMs - ts) / 1000);
  return s < 0 ? 0 : s;
}

function badgeModifier(b: LiveDataSurfaceModel["primaryBadge"]): string {
  switch (b) {
    case "LIVE":
      return "live-data-situation__pill--live";
    case "PAPER":
    case "SHADOW":
      return "live-data-situation__pill--lane";
    case "STALE":
    case "NO_LIVE":
    case "ERROR":
      return "live-data-situation__pill--bad";
    case "PARTIAL":
    case "DEGRADED_READ":
      return "live-data-situation__pill--warn";
    case "LOADING":
    default:
      return "live-data-situation__pill--muted";
  }
}

type Props = Readonly<{
  model: LiveDataSurfaceModel;
}>;

/**
 * Einheitliche Live-Daten-Lage: Spur (Paper/Shadow/Live), Marktdaten-/Feed-Status, Alter, Qualität, Lücken.
 */
export function LiveDataSituationBar({ model }: Props) {
  const { t } = useI18n();
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const id = globalThis.setInterval(() => setNowMs(Date.now()), 1000);
    return () => globalThis.clearInterval(id);
  }, []);

  const completenessPct = useMemo(() => {
    if (model.lineageTotal <= 0) return null;
    return Math.round((100 * model.lineageWithData) / model.lineageTotal);
  }, [model.lineageTotal, model.lineageWithData]);

  const execLabel = t(`live.dataSituation.lane.${model.executionLane}`);
  const marketBadgeKey =
    model.surfaceKind === "signals_list" && model.primaryBadge === "NO_LIVE"
      ? "live.dataSituation.badge.SIGNAL_FEED_EMPTY"
      : `live.dataSituation.badge.${model.primaryBadge}`;

  const srcLabel = t(`live.dataSituation.source.${model.dataSourceSummaryKey}`);

  const lastMarketS = ageSeconds(model.lastMarketIngestTsMs, nowMs);
  const lastServerS = ageSeconds(model.serverTsMs, nowMs);

  const lastMarketText =
    lastMarketS == null
      ? t("live.dataSituation.lastUpdatedNever")
      : t("live.dataSituation.lastUpdatedAgo", { seconds: lastMarketS });

  const lastServerText =
    model.serverTsMs == null
      ? null
      : lastServerS == null
        ? null
        : t("live.dataSituation.serverClockAgo", { seconds: lastServerS });

  const streamText = model.streamStabilityKey
    ? t(model.streamStabilityKey, model.streamStabilityVars)
    : null;

  const mfKey = model.marketFreshnessStatus
    ? `live.terminal.freshness${
        model.marketFreshnessStatus === "live"
          ? "Live"
          : model.marketFreshnessStatus === "delayed"
            ? "Delayed"
            : model.marketFreshnessStatus === "stale"
              ? "Stale"
              : model.marketFreshnessStatus === "dead"
                ? "Dead"
                : model.marketFreshnessStatus === "no_candles"
                  ? "NoCandles"
                  : "UnknownTf"
      }`
    : null;

  const commsPhase = useMemo(
    () => liveDataSurfaceToCommsPhase(model),
    [model],
  );
  const expectation = useMemo(
    () => liveDataSurfaceToExpectation(model),
    [model],
  );

  return (
    <section
      className="live-data-situation"
      aria-label={t("live.dataSituation.title")}
      role="region"
    >
      <div className="live-data-situation__head">
        <strong className="live-data-situation__title">
          {t("live.dataSituation.title")}
        </strong>
        <span className="muted small">{t("live.dataSituation.subtitle")}</span>
      </div>
      <div className="live-data-situation__pills" role="status">
        <span
          className={`live-data-situation__pill live-data-situation__pill--exec live-data-situation__pill--lane-${model.executionLane}`}
          title={t("live.dataSituation.laneHint")}
        >
          {t("live.dataSituation.executionShort")}: {execLabel}
        </span>
        <span
          className={`live-data-situation__pill ${badgeModifier(model.primaryBadge)}`}
          title={t("live.dataSituation.dataBadgeHint")}
        >
          {t(marketBadgeKey)}
        </span>
        {model.demoOrFixture ? (
          <span className="live-data-situation__pill live-data-situation__pill--warn">
            {t("live.dataSituation.demoFixturePill")}
          </span>
        ) : null}
        {model.readDegraded ? (
          <span className="live-data-situation__pill live-data-situation__pill--warn">
            {t("live.dataSituation.degradedReadPill")}
          </span>
        ) : null}
      </div>
      <dl className="live-data-situation__dl">
        <div className="live-data-situation__row">
          <dt>{t("live.dataSituation.sourceLabel")}</dt>
          <dd>{srcLabel}</dd>
        </div>
        <div className="live-data-situation__row">
          <dt>{t("live.dataSituation.lastMarketUpdate")}</dt>
          <dd>{lastMarketText}</dd>
        </div>
        {lastServerText ? (
          <div className="live-data-situation__row">
            <dt>{t("live.dataSituation.serverReference")}</dt>
            <dd>{lastServerText}</dd>
          </div>
        ) : null}
        {mfKey ? (
          <div className="live-data-situation__row">
            <dt>{t("live.dataSituation.qualityLabel")}</dt>
            <dd>{t(mfKey)}</dd>
          </div>
        ) : null}
        {completenessPct != null ? (
          <div className="live-data-situation__row">
            <dt>{t("live.dataSituation.completenessLabel")}</dt>
            <dd>
              {t("live.dataSituation.completenessValue", {
                pct: completenessPct,
                ok: model.lineageWithData,
                total: model.lineageTotal,
              })}
            </dd>
          </div>
        ) : (
          <div className="live-data-situation__row">
            <dt>{t("live.dataSituation.completenessLabel")}</dt>
            <dd>{t("live.dataSituation.completenessNa")}</dd>
          </div>
        )}
        {streamText ? (
          <div className="live-data-situation__row">
            <dt>{t("live.dataSituation.streamLabel")}</dt>
            <dd>{streamText}</dd>
          </div>
        ) : null}
      </dl>
      {model.missingSegmentIds.length > 0 ? (
        <div className="live-data-situation__gap" role="alert">
          <strong>{t("live.dataSituation.missingStreams")}:</strong>{" "}
          <span className="mono-small">{model.missingSegmentIds.join(", ")}</span>
        </div>
      ) : null}
      {model.affectedAreaKeys.length > 0 ? (
        <div className="live-data-situation__affected muted small">
          <strong>{t("live.dataSituation.affected")}:</strong>{" "}
          {model.affectedAreaKeys.map((k) => t(k)).join(" · ")}
        </div>
      ) : null}
      {model.extraHintKeys.length > 0 ? (
        <ul className="live-data-situation__hints muted small">
          {model.extraHintKeys.map((h) => (
            <li key={h.key + JSON.stringify(h.vars ?? {})}>
              {t(h.key, h.vars)}
            </li>
          ))}
        </ul>
      ) : null}
      <footer className="live-data-situation__comms" aria-label={t("systemComms.expectation.sectionTitle")}>
        <div className="live-data-situation__comms-row">
          <span
            className={`system-comms-mini-pill system-comms-mini-pill--${commsPhase}`}
            data-phase={commsPhase}
          >
            {t(`systemComms.phaseLabel.${commsPhase}`)}
          </span>
          <strong className="live-data-situation__comms-title small">
            {t("systemComms.expectation.sectionTitle")}
          </strong>
        </div>
        <p className="muted small live-data-situation__comms-expect">
          {expectation.expectationVars
            ? t(expectation.expectationKey, expectation.expectationVars)
            : t(expectation.expectationKey)}
        </p>
      </footer>
    </section>
  );
}
