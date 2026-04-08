/**
 * Spiegelt Leser-Envelope `status` in Response-Headern (BFF → Browser),
 * damit Monitoring/Netzwerk-Tools `degraded` bei HTTP 200 erkennen.
 * Body bleibt Kanon; Header sind diagnostisch.
 */
export function applyGatewayReadStatusHeaders(
  headers: Headers,
  bodyText: string,
  contentType: string,
): void {
  const ct = contentType.toLowerCase();
  if (!ct.includes("application/json") && !ct.includes("json")) return;
  try {
    const j = JSON.parse(bodyText) as {
      status?: unknown;
      degradation_reason?: unknown;
    };
    if (j.status === "degraded" || j.status === "empty") {
      headers.set("X-Gateway-Read-Status", String(j.status));
      if (
        typeof j.degradation_reason === "string" &&
        j.degradation_reason.length > 0 &&
        j.degradation_reason.length <= 96
      ) {
        const ascii = j.degradation_reason.replace(/[^\x20-\x7E]/g, "_");
        headers.set("X-Gateway-Degradation-Reason", ascii);
      }
    }
  } catch {
    /* kein JSON */
  }
}
