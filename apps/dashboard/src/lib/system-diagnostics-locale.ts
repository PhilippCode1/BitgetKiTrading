import type { Locale } from "@/lib/i18n/config";

import type {
  StaleCheckItem,
  SystemDiagnosticsViewModel,
  SystemOverallStatus,
} from "@/lib/system-diagnostics-view-model";

type Translator = (
  key: string,
  vars?: Record<string, string | number | boolean>,
) => string;

export function localizeDiagnosticsOverallStatus(
  status: SystemOverallStatus,
  t: Translator,
): string {
  if (status === "OK") return t("console.systemHealthMapPage.diagStatusOk");
  if (status === "Warnung")
    return t("console.systemHealthMapPage.diagStatusWarn");
  return t("console.systemHealthMapPage.diagStatusBlocked");
}

export function localizeDiagnosticsReasonKey(key: string, t: Translator): string {
  return t(`console.systemHealthMapPage.diagReason.${key}`);
}

export function localizeStaleCheckLabel(
  item: StaleCheckItem,
  t: Translator,
): string {
  return t(`console.systemHealthMapPage.staleCheck.${item.key}.label`);
}

export function localizeStaleCheckDetail(
  item: StaleCheckItem,
  t: Translator,
): string {
  const suffix = item.stale ? "detailStale" : "detailFresh";
  return t(`console.systemHealthMapPage.staleCheck.${item.key}.${suffix}`);
}

export function localizeWireStatus(value: string, t: Translator): string {
  if (value === "nicht verdrahtet")
    return t("console.systemHealthMapPage.wireStatusNotConfigured");
  if (value === "unbekannt")
    return t("console.systemHealthMapPage.wireStatusUnknown");
  if (value === "__llm_degraded__")
    return t("console.systemHealthMapPage.llmDegraded");
  if (value.startsWith("__alerts_open__:")) {
    const count = value.slice("__alerts_open__:".length);
    return t("console.systemHealthMapPage.alertsOpen", { count });
  }
  if (value === "ok") return t("console.systemHealthMapPage.wireStatusOk");
  if (value === "unknown")
    return t("console.systemHealthMapPage.wireStatusUnknown");
  return value;
}

export function localizeDiagnosticsEmptyLine(
  line: string,
  t: Translator,
): string {
  if (line === "__no_critical_errors__")
    return t("console.systemHealthMapPage.noCriticalErrors");
  if (line === "__no_success_checks__")
    return t("console.systemHealthMapPage.noSuccessChecks");
  if (line === "__service_no_detail__")
    return t("console.systemHealthMapPage.serviceNoDetail");
  if (line.startsWith("__service_ok__:")) {
    const name = line.slice("__service_ok__:".length);
    return t("console.systemHealthMapPage.serviceCheckOk", { name });
  }
  return line;
}

export function localizeDiagnosticsSummary(
  model: SystemDiagnosticsViewModel,
  locale: Locale,
  t: Translator,
): readonly string[] {
  void locale;
  return model.summaryReasonKeys.map((key) => localizeDiagnosticsReasonKey(key, t));
}

const DATA_SOURCE_NAME_KEYS: Record<string, string> = {
  "Market-Stream": "marketStream",
  "Signal-Pipeline": "signalPipeline",
  Orderbook: "orderbook",
  Reconcile: "reconcile",
};

export function localizeDataSourceName(name: string, t: Translator): string {
  const key = DATA_SOURCE_NAME_KEYS[name];
  if (!key) return name;
  return t(`console.systemHealthMapPage.dataSource.${key}`);
}
