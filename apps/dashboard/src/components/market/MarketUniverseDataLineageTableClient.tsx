"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { PipelineLagBadge } from "@/components/market/PipelineLagBadge";
import { VpinSparkline } from "@/components/market/VpinSparkline";
import { consolePath } from "@/lib/console-paths";
import type { CoreSymbolRow } from "@/lib/market-universe-lineage";
import {
  effectivePipelineLagMs,
  pipelineLagBucket,
  type FeedHealthSsePayload,
  pushVpinHistory,
} from "@/lib/market-universe-stream-pulse";
import { startManagedLiveEventSource } from "@/lib/live-event-source";

const CHART_TF = "5m";

type LineageI18n = Readonly<{
  sub: string;
  thSymbol: string;
  thRegistry: string;
  thLive: string;
  thSubscribe: string;
  thTrade: string;
  thStatus: string;
  thChart: string;
  thPipelineLag: string;
  thVpin: string;
  yes: string;
  no: string;
  openChart: string;
  pulseStreamLabel: string;
  pulseLagLabel: string;
  pulseNoSse: string;
  notApplicableRow: string;
}>;

type Props = Readonly<{
  coreRows: readonly CoreSymbolRow[];
  streamSymbol: string;
  i18n: LineageI18n;
}>;

function parseFeedHealthData(data: unknown): FeedHealthSsePayload | null {
  if (!data || typeof data !== "object") {
    return null;
  }
  return data as FeedHealthSsePayload;
}

export function MarketUniverseDataLineageTableClient({
  coreRows,
  streamSymbol,
  i18n,
}: Props) {
  const [lagMs, setLagMs] = useState<number | null>(null);
  const [vpinLast, setVpinLast] = useState<number | null>(null);
  const [vpinHist, setVpinHist] = useState<number[]>([]);
  const [feedSymbol, setFeedSymbol] = useState<string | null>(null);
  const [sseGaveUp, setSseGaveUp] = useState(false);

  const onFeedHealth = useCallback((data: unknown) => {
    const p = parseFeedHealthData(data);
    if (!p) return;
    const sym = String(p.symbol || "")
      .trim()
      .toUpperCase();
    if (sym) {
      setFeedSymbol(sym);
    }
    setLagMs(effectivePipelineLagMs(p));
    const v = p.vpin_toxicity_0_1;
    if (typeof v === "number" && Number.isFinite(v)) {
      setVpinLast(v);
      setVpinHist((h) => pushVpinHistory(h, v));
    }
  }, []);

  useEffect(() => {
    setSseGaveUp(false);
    const sym = (streamSymbol || "BTCUSDT").trim() || "BTCUSDT";
    const ctrl = startManagedLiveEventSource({
      symbol: sym,
      timeframe: CHART_TF,
      handlers: { onFeedHealth },
      onGiveUp: () => {
        setSseGaveUp(true);
      },
    });
    return () => {
      ctrl.close();
    };
  }, [streamSymbol, onFeedHealth]);

  const lagBucket = pipelineLagBucket(lagMs);
  const showRowTelemetry = (rowSym: string) =>
    feedSymbol != null && rowSym.toUpperCase() === feedSymbol.toUpperCase();

  return (
    <>
      <div
        className="market-pulse__strip"
        data-testid="market-pulse-strip"
        aria-label={i18n.pulseStreamLabel}
      >
        <span className="market-pulse__strip-label">
          {i18n.pulseStreamLabel}{" "}
          <span className="mono-small">{(feedSymbol || streamSymbol || "—").toUpperCase()}</span>
        </span>
        {sseGaveUp ? (
          <span className="market-pulse__cell-muted mono-small">
            {i18n.pulseNoSse}
          </span>
        ) : null}
        <PipelineLagBadge
          lagMs={lagMs}
          bucket={lagBucket}
          labelTemplate={i18n.pulseLagLabel}
        />
        <VpinSparkline values={vpinHist} lastVpin={vpinLast} />
      </div>

      <h3 className="market-universe-lineage__sub">{i18n.sub}</h3>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>{i18n.thSymbol}</th>
              <th>{i18n.thRegistry}</th>
              <th>{i18n.thLive}</th>
              <th>{i18n.thSubscribe}</th>
              <th>{i18n.thTrade}</th>
              <th>{i18n.thStatus}</th>
              <th>{i18n.thPipelineLag}</th>
              <th>{i18n.thVpin}</th>
              <th>{i18n.thChart}</th>
            </tr>
          </thead>
          <tbody>
            {coreRows.map((row) => {
              const match = showRowTelemetry(row.symbol);
              return (
                <tr key={row.symbol}>
                  <td className="mono-small">{row.symbol}</td>
                  <td>{row.inRegistry ? i18n.yes : i18n.no}</td>
                  <td>
                    {row.inRegistry
                      ? row.liveEnabled
                        ? i18n.yes
                        : i18n.no
                      : "—"}
                  </td>
                  <td>
                    {row.inRegistry
                      ? row.subscribeEnabled
                        ? i18n.yes
                        : i18n.no
                      : "—"}
                  </td>
                  <td>
                    {row.inRegistry
                      ? row.tradingEnabled
                        ? i18n.yes
                        : i18n.no
                      : "—"}
                  </td>
                  <td>{row.inRegistry ? row.tradingStatus : "—"}</td>
                  <td>
                    {match ? (
                      <PipelineLagBadge
                        lagMs={lagMs}
                        bucket={lagBucket}
                        labelTemplate={i18n.pulseLagLabel}
                      />
                    ) : (
                      <span className="market-pulse__cell-muted">
                        {i18n.notApplicableRow}
                      </span>
                    )}
                  </td>
                  <td>
                    {match ? (
                      <VpinSparkline
                        values={vpinHist}
                        lastVpin={vpinLast}
                      />
                    ) : (
                      <span className="market-pulse__cell-muted">
                        {i18n.notApplicableRow}
                      </span>
                    )}
                  </td>
                  <td>
                    <Link
                      href={`${consolePath("market-universe")}?${new URLSearchParams({ symbol: row.symbol }).toString()}`}
                    >
                      {i18n.openChart}
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
