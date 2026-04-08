import { publicEnv } from "@/lib/env";
import { fetchGatewayUpstream } from "@/lib/gateway-upstream-fetch";
import { serverEnv } from "@/lib/server-env";

/**
 * Prueft, ob der Next.js-Server das Gateway fuer Admin-Lesezugriff authentifizieren kann.
 * Keine Secrets werden an den Browser geleakt.
 */
export async function canAccessAdminViaServer(): Promise<boolean> {
  const auth = serverEnv.gatewayAuthorizationHeader;
  const base = serverEnv.apiGatewayUrl.replace(/\/$/, "");
  if (!auth) return false;
  try {
    const res = await fetchGatewayUpstream("/v1/admin/rules", auth, {
      timeoutMs: 8000,
    });
    return res.ok;
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.warn(
      "[dashboard] GET /v1/admin/rules probe failed (Admin-Nav ausgeblendet)",
      {
        base,
        error: msg,
      },
    );
    return false;
  }
}

/** Admin-Navigation: nur bei gueltiger serverseitiger Gateway-Auth. */
export async function resolveShowAdminNav(): Promise<boolean> {
  if (!publicEnv.enableAdmin) return false;
  return canAccessAdminViaServer();
}

/** Strategie-Lifecycle-Mutationen: gleiche Schwelle wie Admin-Nav. */
export async function resolveStrategyMutationsVisible(): Promise<boolean> {
  if (!publicEnv.enableAdmin) return false;
  return canAccessAdminViaServer();
}
