import { SignJWT } from "jose";

/**
 * Kunden-Portal-Token: gleiche Claims wie in Operator-JWT, aber role/portal -> customer.
 */
export async function signE2eCustomerPortalJwt(
  secret: string,
): Promise<string> {
  if (!secret.trim()) {
    throw new Error("GATEWAY_JWT_SECRET leer (E2E Kunden-Journey)");
  }
  return new SignJWT({
    sub: "e2e-customer-journey",
    role: "customer",
    portal_roles: ["customer"],
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("4h")
    .sign(new TextEncoder().encode(secret));
}
