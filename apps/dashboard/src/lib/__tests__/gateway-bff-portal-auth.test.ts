/** @jest-environment node */

import {
  requireOperatorGatewayAuth,
  requirePortalGatewayAuth,
} from "@/lib/gateway-bff";

jest.mock("@/lib/portal-jwt-server", () => ({
  readPortalAuthorizationFromHeaders: jest.fn(),
}));

jest.mock("@/lib/server-env", () => ({
  serverEnv: {
    gatewayAuthorizationHeader: "Bearer service-token",
  },
}));

import { readPortalAuthorizationFromHeaders } from "@/lib/portal-jwt-server";

const readPortal = readPortalAuthorizationFromHeaders as jest.Mock;

describe("gateway-bff portal auth", () => {
  beforeEach(() => {
    readPortal.mockReset();
  });

  it("requirePortalGatewayAuth lehnt ohne Cookie ab", () => {
    readPortal.mockReturnValue(null);
    const auth = requirePortalGatewayAuth(new Headers());
    expect(auth.ok).toBe(false);
    if (!auth.ok) {
      expect(auth.response.status).toBe(401);
    }
  });

  it("requirePortalGatewayAuth akzeptiert Portal-JWT", () => {
    readPortal.mockReturnValue("Bearer portal-jwt");
    const auth = requirePortalGatewayAuth(new Headers());
    expect(auth.ok).toBe(true);
    if (auth.ok) {
      expect(auth.authorization).toBe("Bearer portal-jwt");
      expect(auth.source).toBe("portal_jwt");
    }
  });

  it("requireOperatorGatewayAuth faellt auf Service-Token zurueck", () => {
    readPortal.mockReturnValue(null);
    const auth = requireOperatorGatewayAuth(new Headers());
    expect(auth.ok).toBe(true);
    if (auth.ok) {
      expect(auth.source).toBe("bff_env");
    }
  });
});
