import { randomUUID } from "crypto";

/**
 * Setzt fehlende X-Request-ID / X-Correlation-ID fuer Gateway-Upstream-Calls.
 * Eingehende Browser-/BFF-Header (Kleinbuchstaben) werden beruecksichtigt.
 */
export function applyGatewayTraceHeaders(
  target: Headers,
  traceSource?: Headers | null,
): void {
  let rid = target.get("X-Request-ID")?.trim();
  if (!rid) {
    rid = traceSource?.get("x-request-id")?.trim() || randomUUID();
    target.set("X-Request-ID", rid);
  }
  let cid = target.get("X-Correlation-ID")?.trim();
  if (!cid) {
    cid = traceSource?.get("x-correlation-id")?.trim() || rid;
    target.set("X-Correlation-ID", cid);
  }
}
