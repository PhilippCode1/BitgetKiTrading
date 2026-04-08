import type { Locale } from "./config";
import { DEFAULT_LOCALE } from "./config";

export type MessageTree = Record<string, unknown>;

function getPath(obj: MessageTree | undefined, path: string[]): unknown {
  let cur: unknown = obj;
  for (const p of path) {
    if (cur === null || typeof cur !== "object" || Array.isArray(cur))
      return undefined;
    cur = (cur as MessageTree)[p];
  }
  return cur;
}

/**
 * Liest verschachtelten Key (z. B. "console.sidebar.overview").
 * Fallback-Kette: gewaehlte Sprache -> DEFAULT_LOCALE -> Key als Rohtext (nur Entwicklungshinweis).
 * Keine KI-Uebersetzung: ausschliesslich statische JSON-Dateien.
 */
export function resolveMessageString(
  messages: MessageTree,
  fallbackMessages: MessageTree,
  key: string,
): string {
  const parts = key.split(".").filter(Boolean);
  const primary = getPath(messages, parts);
  if (typeof primary === "string" && primary.length > 0) return primary;
  const fb = getPath(fallbackMessages, parts);
  if (typeof fb === "string" && fb.length > 0) return fb;
  return key;
}

export function interpolate(
  template: string,
  vars?: Record<string, string | number | boolean>,
): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, name: string) => {
    const v = vars[name];
    return v === undefined || v === null ? `{${name}}` : String(v);
  });
}

export function buildTranslator(
  locale: Locale,
  messages: MessageTree,
  fallback: MessageTree,
) {
  return function t(
    key: string,
    vars?: Record<string, string | number | boolean>,
  ): string {
    const raw = resolveMessageString(messages, fallback, key);
    return interpolate(raw, vars);
  };
}
