/**
 * Oeffentliche Build-/Runtime-Flags: nur Schluessel aus
 * `apps/dashboard/public-env-allowlist.cjs` (siehe next.config.js).
 * Server-BFF → Gateway: `serverEnv.apiGatewayUrl` (API_GATEWAY_URL), niemals Secrets.
 */
function readPublicBool(value: string | undefined, fallback: boolean): boolean {
  return (value ?? String(fallback)).trim().toLowerCase() === "true";
}

function readPositiveInt(value: string | undefined, fallback: number): number {
  const parsed = Number.parseInt((value ?? "").trim(), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function readCsv(value: string | undefined): string[] {
  return (value ?? "")
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
}

/**
 * Localhost-Fallbacks nur in development/test — nie in Production-Build (`next start`),
 * damit Staging/Prod nicht still mit falschen URLs starten.
 */
function allowDevPublicUrlFallback(): boolean {
  const n = process.env.NODE_ENV;
  return n === "development" || n === "test";
}

function readPublicGatewayBase(
  envName: "NEXT_PUBLIC_API_BASE_URL" | "NEXT_PUBLIC_WS_BASE_URL",
): string {
  const raw = (process.env[envName] ?? "").trim();
  if (raw) {
    return raw;
  }
  if (!allowDevPublicUrlFallback()) {
    return "";
  }
  return envName === "NEXT_PUBLIC_WS_BASE_URL"
    ? "ws://127.0.0.1:8000"
    : "http://127.0.0.1:8000";
}

/** Nur unkritische UI-/URL-Felder — niemals Exchange-, Provider- oder Gateway-Secrets. */
export type PublicEnv = Readonly<{
  appName: string;
  apiBaseUrl: string;
  wsBaseUrl: string;
  defaultSymbol: string;
  defaultTimeframe: string;
  defaultMarketFamily: string;
  defaultProduct: string;
  watchlistSymbols: string[];
  enableNews: boolean;
  enableTelegramStatus: boolean;
  livePollIntervalMs: number;
  liveSsePingSec: number;
  /** Globales Feature-Flag; Sichtbarkeit /console/admin: serverseitig (getOperatorSession, nicht public ENV). */
  enableAdmin: boolean;
  /** Spiegelt Gateway COMMERCIAL_TELEGRAM_REQUIRED_FOR_CONSOLE (nur UI-Gate). */
  commercialTelegramRequiredForConsole: boolean;
  /** Deployment-Hinweis fuer Main Console (kein Secret). */
  deploymentProfile: string;
}>;

export const publicEnv: PublicEnv = Object.freeze({
  appName: process.env.NEXT_PUBLIC_APP_NAME ?? "bitget-btc-ai",
  apiBaseUrl: readPublicGatewayBase("NEXT_PUBLIC_API_BASE_URL"),
  wsBaseUrl: readPublicGatewayBase("NEXT_PUBLIC_WS_BASE_URL"),
  defaultSymbol:
    process.env.NEXT_PUBLIC_DEFAULT_SYMBOL ??
    readCsv(process.env.NEXT_PUBLIC_WATCHLIST_SYMBOLS)[0] ??
    "",
  defaultTimeframe: process.env.NEXT_PUBLIC_DEFAULT_TF ?? "1m",
  defaultMarketFamily: process.env.NEXT_PUBLIC_DEFAULT_MARKET_FAMILY ?? "",
  defaultProduct: process.env.NEXT_PUBLIC_DEFAULT_PRODUCT ?? "",
  watchlistSymbols: readCsv(process.env.NEXT_PUBLIC_WATCHLIST_SYMBOLS),
  enableNews: readPublicBool(process.env.NEXT_PUBLIC_ENABLE_NEWS, true),
  enableTelegramStatus: readPublicBool(
    process.env.NEXT_PUBLIC_ENABLE_TELEGRAM_STATUS,
    true,
  ),
  // Fallback wenn SSE nicht laeuft (ms)
  livePollIntervalMs: readPositiveInt(
    process.env.NEXT_PUBLIC_LIVE_POLL_INTERVAL_MS,
    2000,
  ),
  liveSsePingSec: readPositiveInt(
    process.env.NEXT_PUBLIC_LIVE_SSE_PING_SEC,
    15,
  ),
  enableAdmin: readPublicBool(process.env.NEXT_PUBLIC_ENABLE_ADMIN, true),
  commercialTelegramRequiredForConsole: readPublicBool(
    process.env.NEXT_PUBLIC_COMMERCIAL_TELEGRAM_REQUIRED_FOR_CONSOLE,
    false,
  ),
  deploymentProfile: (
    process.env.NEXT_PUBLIC_DEPLOYMENT_PROFILE ?? "local_private"
  ).trim(),
});
