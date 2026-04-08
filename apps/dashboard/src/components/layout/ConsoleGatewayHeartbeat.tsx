"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  circuitBreakerIsOpen,
  fetchWithBackoffRetry,
} from "@/lib/gateway-client-resilience";

type EdgePayload = {
  gatewayHealth?: string;
  operatorHealthProbe?: { ok: boolean } | null;
};

type Props = Readonly<{
  labelOk: string;
  labelDegraded: string;
  labelChecking: string;
  intervalMs?: number;
}>;

/**
 * Leichte Heartbeat-Pruefung gegen /api/dashboard/edge-status (ohne Secrets im Client).
 * Zeigt diskreten Status; nutzt Backoff/Circuit-Breaker aus gateway-client-resilience.
 */
export function ConsoleGatewayHeartbeat({
  labelOk,
  labelDegraded,
  labelChecking,
  intervalMs = 55_000,
}: Props) {
  const [status, setStatus] = useState<"checking" | "ok" | "degraded">(
    "checking",
  );
  const mounted = useRef(true);

  const probe = useCallback(async () => {
    if (circuitBreakerIsOpen()) {
      if (mounted.current) setStatus("degraded");
      return;
    }
    if (mounted.current) setStatus("checking");
    try {
      const res = await fetchWithBackoffRetry(
        "/api/dashboard/edge-status",
        { cache: "no-store" },
        {
          maxRetries: 1,
          baseDelayMs: 500,
        },
      );
      const j = (await res.json()) as EdgePayload;
      const gh = j.gatewayHealth;
      const op = j.operatorHealthProbe;
      const degraded =
        !res.ok || gh === "down" || gh === "error" || (op != null && !op.ok);
      if (mounted.current) setStatus(degraded ? "degraded" : "ok");
    } catch {
      if (mounted.current) setStatus("degraded");
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void probe();
    const id = window.setInterval(() => void probe(), intervalMs);
    return () => {
      mounted.current = false;
      window.clearInterval(id);
    };
  }, [probe, intervalMs]);

  const cls =
    status === "ok"
      ? "console-gateway-heartbeat--ok"
      : status === "degraded"
        ? "console-gateway-heartbeat--bad"
        : "console-gateway-heartbeat--pending";

  const label =
    status === "ok"
      ? labelOk
      : status === "degraded"
        ? labelDegraded
        : labelChecking;

  return (
    <div
      className={`console-gateway-heartbeat ${cls}`}
      role="status"
      aria-live="polite"
      title={label}
    >
      <span className="console-gateway-heartbeat__dot" aria-hidden />
      <span className="console-gateway-heartbeat__text">{label}</span>
    </div>
  );
}
