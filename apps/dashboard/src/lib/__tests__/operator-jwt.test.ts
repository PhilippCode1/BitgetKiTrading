import { SignJWT } from "jose";

import {
  hasAdminSessionFromDashboardEnv,
  resolveDashboardPersonaFromToken,
  resolveOperatorSessionFromToken,
} from "../operator-jwt";

describe("operator-jwt", () => {
  const secret = "unit-test-gateway-jwt-secret-32b!!";
  const enc = new TextEncoder().encode(secret);

  it("treats admin:read with verified HS256 as admin", async () => {
    const token = await new SignJWT({
      gateway_roles: ["admin:read"],
      sub: "op-1",
    })
      .setProtectedHeader({ alg: "HS256" })
      .setSubject("op-1")
      .setIssuedAt()
      .setExpirationTime("2h")
      .sign(enc);
    const s = await resolveOperatorSessionFromToken(`Bearer ${token}`, secret);
    expect(s?.role).toBe("admin");
    expect(s?.sub).toBe("op-1");
  });

  it("blocks customer portal even if gateway_roles claim admin", async () => {
    const token = await new SignJWT({
      gateway_roles: ["admin:write"],
      portal_roles: ["customer"],
    })
      .setProtectedHeader({ alg: "HS256" })
      .setSubject("c1")
      .setIssuedAt()
      .setExpirationTime("2h")
      .sign(enc);
    const s = await resolveOperatorSessionFromToken(token, secret);
    expect(s?.role).toBe("none");
  });

  it("allows super_admin portal with admin role", async () => {
    const token = await new SignJWT({
      gateway_roles: ["admin:read"],
      platform_role: "super_admin",
    })
      .setProtectedHeader({ alg: "HS256" })
      .setSubject("s1")
      .setIssuedAt()
      .setExpirationTime("2h")
      .sign(enc);
    const s = await resolveOperatorSessionFromToken(token, secret);
    expect(s?.role).toBe("admin");
  });

  it("maps portal customer to DashboardPersona customer", async () => {
    const token = await new SignJWT({
      portal_roles: ["customer"],
      gateway_roles: ["billing:read"],
    })
      .setProtectedHeader({ alg: "HS256" })
      .setSubject("cu-1")
      .setIssuedAt()
      .setExpirationTime("2h")
      .sign(enc);
    const p = await resolveDashboardPersonaFromToken(token, secret);
    expect(p).toBe("customer");
  });

  it("hasAdminSessionFromDashboardEnv is false when env is empty", async () => {
    const prev = process.env.DASHBOARD_GATEWAY_AUTHORIZATION;
    const prevS = process.env.GATEWAY_JWT_SECRET;
    try {
      delete process.env.DASHBOARD_GATEWAY_AUTHORIZATION;
      process.env.GATEWAY_JWT_SECRET = secret;
      const ok = await hasAdminSessionFromDashboardEnv();
      expect(ok).toBe(false);
    } finally {
      if (prev === undefined) {
        delete process.env.DASHBOARD_GATEWAY_AUTHORIZATION;
      } else {
        process.env.DASHBOARD_GATEWAY_AUTHORIZATION = prev;
      }
      if (prevS === undefined) {
        delete process.env.GATEWAY_JWT_SECRET;
      } else {
        process.env.GATEWAY_JWT_SECRET = prevS;
      }
    }
  });
});
