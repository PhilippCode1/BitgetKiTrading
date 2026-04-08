/**
 * Strukturierte Server-Logs (Next.js Server Components / Route Handlers).
 * LOG_LEVEL: error | warn | info | debug (default info). LOG_FORMAT: json | plain
 */
import winston from "winston";

import { serverEnv } from "@/lib/server-env";

const service = "dashboard";
const level = serverEnv.logLevel;
const json = serverEnv.logFormat === "json";

const SENSITIVE_LOG_KEYS = new Set([
  "authorization",
  "cookie",
  "set-cookie",
  "x-admin-token",
  "password",
  "token",
]);

/** Rekursiv verschluesseln fuer Logs (keine Secrets in stdout). */
export function redactForLog(value: unknown): unknown {
  if (value === null || value === undefined) return value;
  if (Array.isArray(value)) return value.map(redactForLog);
  if (typeof value === "object") {
    const o = value as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(o)) {
      if (SENSITIVE_LOG_KEYS.has(k.toLowerCase())) {
        out[k] = "[REDACTED]";
      } else {
        out[k] = redactForLog(v);
      }
    }
    return out;
  }
  return value;
}

const jsonFormat = winston.format.combine(
  winston.format.timestamp(),
  winston.format.errors({ stack: true }),
  winston.format.printf((info) =>
    JSON.stringify(
      redactForLog({
        timestamp: info.timestamp,
        level: info.level,
        service,
        message: info.message,
        ...(info.stack ? { stack: info.stack } : {}),
      }) as Record<string, unknown>,
    ),
  ),
);

export function createServerLogger(name: string) {
  return winston.createLogger({
    level,
    defaultMeta: { service, logger: name },
    transports: [
      new winston.transports.Console({
        format: json ? jsonFormat : winston.format.simple(),
      }),
    ],
  });
}
