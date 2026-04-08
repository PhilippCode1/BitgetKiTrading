import type { Locale } from "./config";
import { DEFAULT_LOCALE } from "./config";
import type { MessageTree } from "./resolve-message";

import de from "@/messages/de.json";
import en from "@/messages/en.json";

const CATALOG: Record<Locale, MessageTree> = {
  de: de as MessageTree,
  en: en as MessageTree,
};

export function getMessagesForLocale(locale: Locale): {
  messages: MessageTree;
  fallback: MessageTree;
} {
  const primary = CATALOG[locale] ?? CATALOG[DEFAULT_LOCALE];
  const fallback = CATALOG[DEFAULT_LOCALE];
  return { messages: primary, fallback };
}
