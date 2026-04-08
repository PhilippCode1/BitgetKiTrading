"use client";

import { Suspense } from "react";

import { ConsoleFetchNoticeActions } from "@/components/console/ConsoleFetchNoticeActions";

/** Schnellaktionen unter einer Systemstatus-Karte (Server-Komponente + Client-Insel). */
export function SystemStatusCardActions() {
  return (
    <Suspense fallback={null}>
      <ConsoleFetchNoticeActions />
    </Suspense>
  );
}
