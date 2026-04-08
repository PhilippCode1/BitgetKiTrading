"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";

import {
  DEFAULT_LOCALE,
  LOCALE_STORAGE_KEY,
  type Locale,
} from "@/lib/i18n/config";
import { buildTranslator } from "@/lib/i18n/resolve-message";
import type { MessageTree } from "@/lib/i18n/resolve-message";

import { mirrorLocalePreferenceToServer } from "@/lib/client/best-effort-fetch";
import de from "@/messages/de.json";
import en from "@/messages/en.json";

const TREES: Record<Locale, MessageTree> = {
  de: de as MessageTree,
  en: en as MessageTree,
};

export type TranslateFn = (
  key: string,
  vars?: Record<string, string | number | boolean>,
) => string;

type I18nContextValue = Readonly<{
  locale: Locale;
  t: TranslateFn;
  setLocale: (loc: Locale) => Promise<void>;
}>;

const I18nContext = createContext<I18nContextValue | null>(null);

type Props = Readonly<{
  initialLocale: Locale;
  children: ReactNode;
}>;

export function I18nProvider({ initialLocale, children }: Props) {
  const [locale, setLoc] = useState<Locale>(initialLocale);
  const router = useRouter();

  const t = useMemo(
    () => buildTranslator(locale, TREES[locale], TREES[DEFAULT_LOCALE]),
    [locale],
  );

  const setLocale = useCallback(
    async (loc: Locale) => {
      const res = await fetch("/api/locale", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ locale: loc }),
      });
      if (!res.ok) {
        const j = (await res.json().catch(() => ({}))) as { error?: string };
        throw new Error(j.error || `HTTP ${res.status}`);
      }
      try {
        localStorage.setItem(LOCALE_STORAGE_KEY, loc);
      } catch {
        /* private mode */
      }
      await mirrorLocalePreferenceToServer(loc);
      setLoc(loc);
      router.refresh();
    },
    [router],
  );

  const value = useMemo<I18nContextValue>(
    () => ({ locale, t, setLocale }),
    [locale, t, setLocale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useI18n must be used within I18nProvider");
  }
  return ctx;
}
