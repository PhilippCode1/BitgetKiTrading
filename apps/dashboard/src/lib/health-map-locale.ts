import type { Locale } from "@/lib/i18n/config";

import type {
  HealthMapComponentView,
  HealthMapView,
} from "@/lib/health-map-view-model";

/** Blocker-Zeilen fuer die Health-Landkarte (DE/EN). */
export function healthMapBlockerReasons(
  model: HealthMapView,
  locale: Locale,
): readonly string[] {
  return locale === "en" ? model.blocker_gründe_en : model.blocker_gründe_de;
}

export type LocalizedHealthMapComponent = Readonly<{
  komponente: string;
  liveImpact: string;
  errorReason: string;
  nextStep: string;
  blockiert_live: boolean;
  status: HealthMapComponentView["status"];
  freshness_status: HealthMapComponentView["freshness_status"];
}>;

/** Einzelne Komponentenzeile fuer UI (DE/EN-Felder aus dem View-Model). */
export function localizeHealthMapComponent(
  row: HealthMapComponentView,
  locale: Locale,
): LocalizedHealthMapComponent {
  const en = locale === "en";
  return {
    komponente: row.komponente,
    liveImpact: en ? row.live_auswirkung_en : row.live_auswirkung_de,
    errorReason: en ? row.fehlergrund_en : row.fehlergrund_de,
    nextStep: en ? row.nächster_schritt_en : row.nächster_schritt_de,
    blockiert_live: row.blockiert_live,
    status: row.status,
    freshness_status: row.freshness_status,
  };
}
