import type { Locale } from "@/lib/i18n/config";

import type { OperatorAlertView } from "@/lib/operator-alerts-view-model";

export type LocalizedOperatorAlertText = Readonly<{
  title: string;
  description: string;
  recommended: string;
  nextStep: string;
}>;

/** Picks DE/EN alert copy; EN fields fall back to DE when missing. */
export function localizeOperatorAlert(
  alert: OperatorAlertView,
  locale: Locale,
): LocalizedOperatorAlertText {
  if (locale === "en") {
    return {
      title: alert.titel_en,
      description: alert.beschreibung_en,
      recommended: alert.empfohlene_aktion_en,
      nextStep: alert.nächster_sicherer_schritt_en,
    };
  }
  return {
    title: alert.titel_de,
    description: alert.beschreibung_de,
    recommended: alert.empfohlene_aktion_de,
    nextStep: alert.nächster_sicherer_schritt_de,
  };
}
