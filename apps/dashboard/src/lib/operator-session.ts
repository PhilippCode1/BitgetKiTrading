import { publicEnv } from "@/lib/env";
import {
  type OperatorSession,
  resolveOperatorSessionFromToken,
} from "@/lib/operator-jwt";
import { serverEnv } from "@/lib/server-env";

export type { OperatorSession };

/**
 * Kryptographisch bzw. serverseitig gepruefter Operator-Status (DASHBOARD_GATEWAY_AUTHORIZATION).
 * `role === 'admin'` gemaess gateway_roles (admin:read|write) und ohne Kunden-Portal-Block (customer in portal_roles).
 * Kein Abgleich mit NEXT_PUBLIC_*-Build-Flags.
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
