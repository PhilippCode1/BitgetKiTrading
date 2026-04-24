import type { NextRequest } from "next/server";

import { decideConsoleAccess } from "../middleware-console-guard";
import { getDashboardPersonaFromRequest } from "../portal-persona";
import { PORTAL_BASE } from "../console-paths";

jest.mock("../portal-persona", () => ({
  getDashboardPersonaFromRequest: jest.fn(),
  PORTAL_JWT_COOKIE_NAME: "bitget_portal_jwt",
  getDashboardPersonaForServerComponent: jest.fn(),
}));

const mockPersona = getDashboardPersonaFromRequest as jest.MockedFunction<
  typeof getDashboardPersonaFromRequest
>;

/**
 * Bedrohungsmodell: Token/Cookie im Browser manipulierbar — ein Endkunde setzt
 * (oder ersetzt) `bitget_portal_jwt` so, dass nach HS256-Verify die Persona
 * `customer` entsteht (role=customer und/oder portal_roles) und surft zu
 * `/console/health` (System-Health, Operator-only).
 * Erwartung: Middleware-Gate liefert Redirect auf {@link PORTAL_BASE}, bevor
 * der Operator-Layout-Tree (Heartbeat, Systemstatus) geraendert wird.
 */
describe("decideConsoleAccess (Kunden-Block /console/*)", () => {
  const dummy = {} as NextRequest;

  beforeEach(() => {
    mockPersona.mockReset();
  });

  it("durchreichen: kein /console Pfade", async () => {
    mockPersona.mockResolvedValue("customer");
    await expect(
      decideConsoleAccess(dummy, "/portal/billing"),
    ).resolves.toEqual({ action: "next" });
  });

  it("Kunde -> Redirect von /console/health weg (Mock: getDashboardPersonaFromRequest=customer)", async () => {
    mockPersona.mockResolvedValue("customer");
    const r = await decideConsoleAccess(dummy, "/console/health");
    expect(r).toEqual({ action: "redirect", location: PORTAL_BASE });
  });

  it("Operateur -> /console/health zulaessig (Mock: operator)", async () => {
    mockPersona.mockResolvedValue("operator");
    await expect(
      decideConsoleAccess(dummy, "/console/health"),
    ).resolves.toEqual({ action: "next" });
  });
});
