/**
 * Zentrale Allowlists fuer Dashboard-BFF → API-Gateway.
 * Eine Quelle fuer Dokumentation, Tests und Route-Handler (keine divergierenden Sets).
 */

/** Einziger POST-Zielbaum fuer den generischen Gateway-Catch-All (`gateway/[...segments]`). */
export const GENERIC_GATEWAY_BFF_POST_PATH_PREFIX =
  "/v1/commerce/customer/contracts" as const;

/**
 * true genau fuer `.../contracts` und `.../contracts/*`, nicht fuer z. B. `.../contracts-foo`.
 */
export function genericGatewayBffAllowsPostPath(path: string): boolean {
  return (
    path === GENERIC_GATEWAY_BFF_POST_PATH_PREFIX ||
    path.startsWith(`${GENERIC_GATEWAY_BFF_POST_PATH_PREFIX}/`)
  );
}

/** POST-Ziele fuer `/api/dashboard/admin/commerce-mutation` (Body: method, path, payload). */
export const COMMERCE_ADMIN_MUTATION_ALLOWED_POST_PATHS = new Set<string>([
  "/v1/commerce/admin/customer/lifecycle/transition",
  "/v1/commerce/admin/customer/wallet/adjust",
  "/v1/commerce/admin/customer/lifecycle/set-email-verified",
]);

export const COMMERCE_ADMIN_MUTATION_DUNNING_PATCH_RE =
  /^\/v1\/commerce\/admin\/billing\/tenant\/[^/]+\/dunning$/;

export function commerceAdminMutationAllowed(
  method: string,
  path: string,
): boolean {
  const m = method.toUpperCase();
  if (m === "POST") {
    return COMMERCE_ADMIN_MUTATION_ALLOWED_POST_PATHS.has(path);
  }
  if (m === "PATCH") {
    return COMMERCE_ADMIN_MUTATION_DUNNING_PATCH_RE.test(path);
  }
  return false;
}
