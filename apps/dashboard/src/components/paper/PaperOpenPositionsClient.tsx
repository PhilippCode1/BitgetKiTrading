"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { OpenPositionsTable } from "@/components/tables/OpenPositionsTable";
import { fetchPaperOpen } from "@/lib/api";
import { publicEnv } from "@/lib/env";
import { startManagedLiveEventSource } from "@/lib/live-event-source";
import {
  fetchAndApplyTradeLifecycleCaches,
  isPaperSseForTradeLifecycle,
  paperOpenQueryKey,
} from "@/lib/live-broker-console";
import type { PaperOpenResponse } from "@/lib/types";

type Props = Readonly<{
  symbol: string;
  initial: PaperOpenResponse;
}>;

/**
 * Paper-Seite: TanStack-Cache + SSE-Event `paper` (Gateway: trade_* = payload_trade_lifecycle).
 * fetchAndApplyTradeLifecycleCaches setzt u.a. paperOpenQueryKey per setQueryData.
 */
export function PaperOpenPositionsClient({ symbol, initial }: Props) {
  const queryClient = useQueryClient();
  const sym = symbol.trim() || publicEnv.defaultSymbol || "BTCUSDT";
  const tf = publicEnv.defaultTimeframe || "1m";

  const { data = initial } = useQuery({
    queryKey: paperOpenQueryKey(sym),
    queryFn: async () => fetchPaperOpen(sym),
    initialData: initial,
    placeholderData: (prev) => prev,
    staleTime: 5_000,
  });

  useEffect(() => {
    const ctrl = startManagedLiveEventSource({
      symbol: sym,
      timeframe: tf,
      handlers: {
        onPaper: (raw) => {
          if (!isPaperSseForTradeLifecycle(raw)) {
            return;
          }
          void fetchAndApplyTradeLifecycleCaches(queryClient, {
            symbol: sym,
            timeframe: tf,
            limit: 500,
          });
        },
        onPing: () => {},
      },
    });
    return () => ctrl.close();
  }, [queryClient, sym, tf]);

  return <OpenPositionsTable positions={data.positions} isLoading={false} />;
}
