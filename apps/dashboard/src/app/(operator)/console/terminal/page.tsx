import { Suspense } from "react";

import { HealthSnapshotLoadNotice } from "@/components/console/HealthSnapshotLoadNotice";
import { LiveTerminalClient } from "@/components/live/LiveTerminalClient";
import { fetchLiveState, fetchSystemHealthBestEffort } from "@/lib/api";
import { diagnosticFromSearchParams } from "@/lib/console-params";
import { executionPathFromSystemHealth } from "@/lib/execution-path-view-model";
import { publicEnv } from "@/lib/env";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { emptyLiveStateResponse } from "@/lib/live-state-defaults";
import { fetchLiveTerminalServerMeta } from "@/lib/live-terminal-server-meta";
import { resolveTradeSymbol } from "@/lib/resolve-trade-symbol";
import type { LiveStateResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

type SP = Record<string, string | string[] | undefined>;

function first(sp: SP, key: string): string | undefined {
  const value = sp[key];
  return Array.isArray(value) ? value[0] : value;
}

export default async function TerminalPage({
  searchParams,
}: {
  searchParams: SP | Promise<SP>;
}) {
  const t = await getServerTranslator();
  const sp = await Promise.resolve(searchParams);
  const diagnostic = diagnosticFromSearchParams(sp);
  const symbol = resolveTradeSymbol(first(sp, "symbol"));
  const timeframe =
    first(sp, "timeframe")?.trim() || publicEnv.defaultTimeframe || "1m";
  const symbolOptions = Array.from(
    new Set([
      symbol,
      resolveTradeSymbol(publicEnv.defaultSymbol),
      ...publicEnv.watchlistSymbols,
    ]),
  )
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
  let initialLoadError: string | null = null;
  let initial: LiveStateResponse;
  const liveTerminalMeta = await fetchLiveTerminalServerMeta();
  const { health, error: healthLoadError } =
    await fetchSystemHealthBestEffort();
  const executionVm = executionPathFromSystemHealth(health);
  try {
    initial = await fetchLiveState({
      symbol,
      timeframe,
      limit: 500,
    });
  } catch (e) {
    initialLoadError =
      e instanceof Error ? e.message : t("pages.terminal.loadErrFallback");
    initial = emptyLiveStateResponse(symbol, timeframe);
  }
  return (
    <Suspense
      fallback={
        <p className="muted" role="status">
          {t("live.terminal.loadingShell")}
        </p>
      }
    >
      <HealthSnapshotLoadNotice
        error={healthLoadError}
        diagnostic={diagnostic}
        t={t}
      />
      <LiveTerminalClient
        initial={initial}
        initialLoadError={initialLoadError}
        symbolOptions={symbolOptions}
        liveTerminalMeta={liveTerminalMeta}
        executionVm={executionVm}
      />
    </Suspense>
  );
}
