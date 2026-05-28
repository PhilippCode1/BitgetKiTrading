/** Idempotente GET-Retry-Policy (Browser-BFF + Server-Upstream). Kein server-only. */

const GET_RETRYABLE_HTTP_STATUS = new Set([408, 429, 502, 503, 504]);

export function isRetryableGatewayGetStatus(status: number): boolean {
  return GET_RETRYABLE_HTTP_STATUS.has(status);
}
