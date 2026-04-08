/**
 * Fail-fast beim Server-Start (instrumentation): keine stillen 503 im UI durch fehlende Gateway-ENV.
 * Aktiv wenn NODE_ENV=production oder DASHBOARD_ENFORCE_ENV=true (lokal strikt testen).
 */

function bad(val: string | undefined): boolean {
  const t = (val ?? "").trim();
  if (!t) return true;
  const u = t.toUpperCase();
  return u.includes("<SET_ME>") || u === "SET_ME" || u === "CHANGE_ME";
}

function enforceRuntime(): boolean {
  if (process.env.NODE_ENV === "production") return true;
  return process.env.DASHBOARD_ENFORCE_ENV?.trim().toLowerCase() === "true";
}

/**
 * Wirft mit klarer Meldung, wenn Pflicht-ENV fuer den Dashboard-Server fehlt.
 */
export function assertDashboardRuntimeEnvOrThrow(): void {
  if (!enforceRuntime()) {
    return;
  }
  const errors: string[] = [];
  if (bad(process.env.API_GATEWAY_URL)) {
    errors.push(
      "API_GATEWAY_URL fehlt oder Platzhalter (serverseitige Gateway-Basis).",
    );
  }
  if (bad(process.env.DASHBOARD_GATEWAY_AUTHORIZATION)) {
    errors.push(
      "DASHBOARD_GATEWAY_AUTHORIZATION fehlt — Bearer-JWT (gateway:read), z. B. mint_dashboard_gateway_jwt.py",
    );
  }
  if (bad(process.env.NEXT_PUBLIC_API_BASE_URL)) {
    errors.push(
      "NEXT_PUBLIC_API_BASE_URL fehlt (Build-/Runtime oeffentliche API-Basis).",
    );
  }
  if (bad(process.env.NEXT_PUBLIC_WS_BASE_URL)) {
    errors.push(
      "NEXT_PUBLIC_WS_BASE_URL fehlt (oeffentliche WebSocket-Basis).",
    );
  }
  if (errors.length === 0) {
    return;
  }
  const msg = [
    "[dashboard] Start abgebrochen — ungueltige oder unvollstaendige ENV:",
    ...errors.map((e) => `  - ${e}`),
    "",
    "Dokumentation: docs/CONFIGURATION.md",
  ].join("\n");
  throw new Error(msg);
}
