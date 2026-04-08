import { getMessagesForLocale } from "@/lib/i18n/load-messages";
import { buildTranslator } from "@/lib/i18n/resolve-message";

import { getRequestLocale } from "./server";

/** Server Components: einheitlicher Zugriff auf statische messages/*.json (kein KI-Translate). */
export async function getServerTranslator() {
  const locale = await getRequestLocale();
  const { messages, fallback } = getMessagesForLocale(locale);
  return buildTranslator(locale, messages, fallback);
}
