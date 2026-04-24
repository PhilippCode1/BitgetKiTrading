import { publicEnv } from "@/lib/env";
import {
  type OperatorSession,
  resolveOperatorSessionFromToken,
} from "@/lib/operator-jwt";
import { serverEnv } from "@/lib/server-env";

export type { OperatorSession };

/**
 * BFF-Operator-Identitaet: `DASHBOARD_GATEWAY_AUTHORIZATION` (kein Browser-Cookie).
 * `role === 'admin'` gemaess gateway_roles + role-Claim; Kunden-Portal-Block bei customer in portal_roles.
 *
 * Endkunden-UI: (customer)/portal, Persona via Cookie `bitget_portal_jwt` —
 * `getDashboardPersonaForServerComponent` (portal-persona) / `useCustomerPortalPersona`.
 * Middleware blockt /console/* fuer Kunden.
 */
export async function getOperatorSession(): Promise<OperatorSession | null> {
  return resolveOperatorSessionFromToken(
    serverEnv.gatewayAuthorizationHeader,
    serverEnv.gatewayJwtSecret,
  );
}

/**
 * @deprecated zugunsten getOperatorSession() / role === "admin" — Bezeichnung bleibt fuer bestehende Server-Components.
 */
export async function canAccessAdminViaServer(): Promise<boolean> {
  if (!publicEnv.enableAdmin) {
    return false;
  }
  const s = await getOperatorSession();
  return s?.role === "admin";
}

/** Admin-Navigation: nur bei gueltigem Admin-Claim in DASHBOARD_GATEWAY_AUTHORIZATION. */
export async function resolveShowAdminNav(): Promise<boolean> {
  if (!publicEnv.enableAdmin) {
    return false;
  }
  const s = await getOperatorSession();
  return s?.role === "admin";
}

/** Strategie-Lifecycle-Mutationen: gleiche Schwelle wie Admin-Nav. */
export async function resolveStrategyMutationsVisible(): Promise<boolean> {
  if (!publicEnv.enableAdmin) {
    return false;
  }
  const s = await getOperatorSession();
  return s?.role === "admin";
}
