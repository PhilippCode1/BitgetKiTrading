import type { NextRequest } from "next/server";

import { PORTAL_BASE } from "@/lib/console-paths";
import { getDashboardPersonaFromRequest } from "@/lib/portal-persona";

export type ConsoleAccessDecision =
  | { action: "next" }
  | { action: "redirect"; location: string };

/**
 * Endkunden (portal_roles customer und/oder JWT-Claim role=customer) duerfen
 * /console/* nicht — nur Operator- und BFF-Pfade.
 */
export async function decideConsoleAccess(
  request: NextRequest,
  pathname: string,
): Promise<ConsoleAccessDecision> {
  if (!pathname.startsWith("/console")) {
    return { action: "next" };
  }
  const persona = await getDashboardPersonaFromRequest(request);
  if (persona === "customer") {
    return { action: "redirect", location: PORTAL_BASE };
  }
  return { action: "next" };
}
