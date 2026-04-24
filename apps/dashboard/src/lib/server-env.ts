/**
 * Laufzeit-Only: `API_GATEWAY_URL`, `DASHBOARD_GATEWAY_AUTHORIZATION`, `GATEWAY_JWT_SECRET` u. a. —
 * gehoeren nicht in die oeffentliche Next-Allowlist (siehe `public-env-allowlist.cjs` + `lib/env.ts`).
 */
const SERVER_LOG_LEVELS = ["error", "warn", "info", "debug"] as const;

export type ServerLogLevel = (typeof SERVER_LOG_LEVELS)[number];
export type ServerLogFormat = "json" | "plain";

/**
 * Wahr, wenn die API-Basis weder localhost noch 127.0.0.1 ist (Production-Paritaet, kein BFF-Loopback).
 */
function isLoopbackApiBase(url: string): boolean {
  try {
    const u = new URL(url);
    const h = u.hostname.toLowerCase();
    return h === "localhost" || h === "127.0.0.1" || h === "::1";
  } catch {
    return false;
  }
}

/**
 * Server-zu-Gateway: `API_GATEWAY_URL` hat Vorrang.
 * Bei `NODE_ENV==='production'`: kein stilles Umschalten auf NEXT_PUBLIC_* und
 * kein fester 127.0.0.1:8000-Fallback — ohne gesetzte, nicht-Loopback-API_GATEWAY_URL
 * ist das Ergebnis bewusst leer (Build-Drift vermeiden).
 * Nur in development/test: optional NEXT_PUBLIC_API_BASE_URL oder lokaler 127.0.0.1:8000.
 */
function readApiGatewayUrl(): string {
  const isProd = process.env.NODE_ENV === "production";
  const primary = (process.env.API_GATEWAY_URL ?? "").trim().replace(/\/$/, "");
  if (primary) {
    if (isProd && isLoopbackApiBase(primary)) {
      if (process.env.ALLOW_API_GATEWAY_LOOPBACK_IN_PRODUCTION === "true") {
        return primary;
      }
      return "";
    }
    return primary;
  }
  if (isProd) {
    return "";
  }
  const n = process.env.NODE_ENV;
  if (n !== "development" && n !== "test") {
    return "";
  }
  const pub = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "")
    .trim()
    .replace(/\/$/, "");
  if (pub) {
    return pub;
  }
  return "http://127.0.0.1:8000";
}

function readServerLogLevel(): ServerLogLevel {
  const normalized = (process.env.LOG_LEVEL ?? "info").trim().toLowerCase();
  if (SERVER_LOG_LEVELS.includes(normalized as ServerLogLevel)) {
    return normalized as ServerLogLevel;
  }
  return "info";
}

function readServerLogFormat(): ServerLogFormat {
  return (process.env.LOG_FORMAT ?? "plain").trim().toLowerCase() === "json"
    ? "json"
    : "plain";
}

function readGatewayAuthHeader(): string | undefined {
  const v = (process.env.DASHBOARD_GATEWAY_AUTHORIZATION ?? "").trim();
  return v || undefined;
}

/** Gleiche HS256-Quelle wie api-gateway / mint_dashboard_gateway_jwt.py (kein Leak an den Client). */
function readGatewayJwtSecret(): string | undefined {
  const v = (process.env.GATEWAY_JWT_SECRET ?? "").trim();
  return v || undefined;
}

function readPaymentMockWebhookSecret(): string {
  return (process.env.PAYMENT_MOCK_WEBHOOK_SECRET ?? "").trim();
}

function readCommercialTelegramRequired(): boolean {
  return (
    (process.env.COMMERCIAL_TELEGRAM_REQUIRED_FOR_CONSOLE ?? "")
      .trim()
      .toLowerCase() === "true"
  );
}

export const serverEnv = Object.freeze({
  logLevel: readServerLogLevel(),
  logFormat: readServerLogFormat(),
  apiGatewayUrl: readApiGatewayUrl(),
  /** Server-only Authorization-Header fuer API-Gateway (z. B. Bearer JWT). Nicht exponieren. */
  gatewayAuthorizationHeader: readGatewayAuthHeader(),
  /** Wie `GATEWAY_JWT_SECRET` im API-Gateway; fuer BFF-Validierung der Operator-JWT-Claims. */
  gatewayJwtSecret: readGatewayJwtSecret(),
  /** Server-only: Mock-Einzahlung abschliessen (gleiches Secret wie Gateway). */
  paymentMockWebhookSecret: readPaymentMockWebhookSecret(),
  /** Spiegelt Gateway: ohne Telegram nur Konto-Bereich in der Console. */
  commercialTelegramRequiredForConsole: readCommercialTelegramRequired(),
});
