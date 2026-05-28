const KNOWN_CODES = new Set([
  "oidc_not_configured",
  "oidc_start_failed",
  "mock_login_disabled",
  "invalid_tenant_id",
  "missing_gateway_jwt_secret",
  "sign_failed",
]);

type TranslateFn = (key: string, params?: Record<string, string>) => string;

/** Maps server login action error codes to localized UI strings. */
export function loginErrorMessage(t: TranslateFn, errorCode: string): string {
  if (KNOWN_CODES.has(errorCode)) {
    return t(`public.login.errors.${errorCode}`);
  }
  return t("public.login.unknownError");
}
