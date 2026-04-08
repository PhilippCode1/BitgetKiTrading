const SERVER_LOG_LEVELS = ["error", "warn", "info", "debug"] as const;

export type ServerLogLevel = (typeof SERVER_LOG_LEVELS)[number];
export type ServerLogFormat = "json" | "plain";

/**
 * Server-zu-Gateway: `API_GATEWAY_URL` hat Vorrang. Fallback auf NEXT_PUBLIC_* oder Loopback
 * nur in development/test — in Production (`next start`) leer lassen, wenn unset (fail-fast am BFF).
 */
function readApiGatewayUrl(): string {
  const primary = (process.env.API_GATEWAY_URL ?? "").trim().replace(/\/$/, "");
  if (primary) {
    return primary;
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
  /** Server-only: Mock-Einzahlung abschliessen (gleiches Secret wie Gateway). */
  paymentMockWebhookSecret: readPaymentMockWebhookSecret(),
  /** Spiegelt Gateway: ohne Telegram nur Konto-Bereich in der Console. */
  commercialTelegramRequiredForConsole: readCommercialTelegramRequired(),
});
