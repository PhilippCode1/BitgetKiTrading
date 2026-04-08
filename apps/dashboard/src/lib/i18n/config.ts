/**
 * UI-Sprachen: statische Kataloge unter src/messages/*.json.
 * Keine KI-Uebersetzung zur Laufzeit — Fallback immer auf diese Dateien (siehe resolve-message.ts).
 */

export const SUPPORTED_LOCALES = ["de", "en"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "de";

export const LOCALE_COOKIE_NAME = "bitget_dashboard_locale";
export const LOCALE_STORAGE_KEY = "bitget_dashboard_locale";

export function isLocale(value: string | null | undefined): value is Locale {
  return value === "de" || value === "en";
}

/** Architektur-Erweiterung: weitere Locales hier + messages/<locale>.json + SUPPORTED_LOCALES. */
export const LOCALE_LABELS: Record<Locale, string> = {
  de: "Deutsch",
  en: "English",
};
