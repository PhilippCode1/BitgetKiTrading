/**
 * Browser-seitige Resilienz fuer BFF-/Gateway-Aufrufe: Backoff-Retry und einfacher Circuit-Breaker.
 * Pro Tab (Modul-Singleton); verhindert Request-Stuerme bei hartem Ausfall.
 */

const DEFAULT_FAILURE_THRESHOLD = 3;
const DEFAULT_COOLDOWN_MS = 45_000;
const DEFAULT_MAX_RETRIES = 2;
const DEFAULT_BASE_DELAY_MS = 400;

type BreakerState = {
  failures: number;
  openUntil: number;
};

const breaker: BreakerState = { failures: 0, openUntil: 0 };

export function circuitBreakerIsOpen(now = Date.now()): boolean {
  if (now < breaker.openUntil) return true;
  if (breaker.openUntil > 0 && now >= breaker.openUntil) {
    breaker.failures = 0;
    breaker.openUntil = 0;
  }
  return false;
}

export function circuitBreakerRecordSuccess(): void {
  breaker.failures = 0;
  breaker.openUntil = 0;
}

export function circuitBreakerRecordFailure(
  now = Date.now(),
  threshold = DEFAULT_FAILURE_THRESHOLD,
  cooldownMs = DEFAULT_COOLDOWN_MS,
): void {
  breaker.failures += 1;
  if (breaker.failures >= threshold) {
    breaker.openUntil = now + cooldownMs;
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

export type ResilientFetchOptions = Readonly<{
  maxRetries?: number;
  baseDelayMs?: number;
  /** Wenn true, keine Retries (z. B. nach Breaker-Open). */
  skipRetry?: boolean;
}>;

/**
 * fetch mit exponentiellem Backoff (nur bei Netzwerk-/Timeout-Fehlern, nicht bei HTTP 4xx).
 */
export async function fetchWithBackoffRetry(
  input: RequestInfo | URL,
  init: RequestInit | undefined,
  opts: ResilientFetchOptions = {},
): Promise<Response> {
  const maxRetries = opts.maxRetries ?? DEFAULT_MAX_RETRIES;
  const baseDelayMs = opts.baseDelayMs ?? DEFAULT_BASE_DELAY_MS;
  const skipRetry = opts.skipRetry ?? false;

  let lastErr: unknown;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch(input, init);
      if (res.ok) {
        circuitBreakerRecordSuccess();
        return res;
      }
      const retryable = res.status >= 502 || res.status === 429;
      if (!retryable || skipRetry || attempt === maxRetries) {
        if (res.status >= 502) circuitBreakerRecordFailure();
        return res;
      }
    } catch (e) {
      lastErr = e;
      if (skipRetry || attempt === maxRetries) {
        circuitBreakerRecordFailure();
        throw e;
      }
    }
    const jitter = Math.random() * 120;
    await sleep(baseDelayMs * 2 ** attempt + jitter);
  }
  circuitBreakerRecordFailure();
  throw lastErr instanceof Error ? lastErr : new Error(String(lastErr));
}
