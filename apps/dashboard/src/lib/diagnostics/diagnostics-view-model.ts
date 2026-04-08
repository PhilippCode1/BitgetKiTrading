import type {
  SelfHealingComponentRow,
  SelfHealingIncident,
  SelfHealingSnapshot,
} from "@/lib/self-healing/schema";

/** Geschäftskritikalität: 0 = höchste Priorität (P0). */
export type DiagnosticBusinessTier = 0 | 1 | 2 | 3;

export type DiagnosticFilterId =
  | "critical_only"
  | "unresolved_only"
  | "live_relevant"
  | "data_only"
  | "broker_auth";

const P0 = new Set([
  "gateway_edge",
  "dashboard_bff",
  "api_gateway",
  "operator_jwt_auth",
  "postgres",
  "gateway_ready",
  "readiness_core",
]);

const P1 = new Set([
  "redis",
  "eventbus_streams",
  "live_broker",
  "paper_broker",
  "live_reconcile",
  "gateway_health_http",
]);

const LIVE_RELEVANT = new Set([
  "live_broker",
  "paper_broker",
  "live_reconcile",
  "gateway_ready",
  "operator_jwt_auth",
  "market_stream",
  "data_freshness_candles",
  "data_freshness_signals",
  "signal_engine",
  "readiness_core",
  "eventbus_streams",
]);

const DATA_IDS = new Set([
  "postgres",
  "redis",
  "migrations",
  "data_freshness_candles",
  "data_freshness_signals",
  "data_freshness_news",
  "eventbus_streams",
]);

const BROKER_AUTH_IDS = new Set([
  "live_broker",
  "paper_broker",
  "operator_jwt_auth",
  "live_reconcile",
  "external_integrations",
]);

export function businessTierForComponentId(id: string): DiagnosticBusinessTier {
  if (P0.has(id)) return 0;
  if (P1.has(id)) return 1;
  if (
    id.startsWith("data_freshness") ||
    id.includes("engine") ||
    id === "market_stream"
  ) {
    return 2;
  }
  return 3;
}

export function isCriticalComponent(row: SelfHealingComponentRow): boolean {
  return (
    row.status === "down" ||
    row.status === "degraded" ||
    row.manualRemediationRequired
  );
}

export function isUnresolvedComponent(row: SelfHealingComponentRow): boolean {
  if (row.manualRemediationRequired) return true;
  return row.status !== "ok";
}

export function rowMatchesFilter(
  row: SelfHealingComponentRow,
  active: ReadonlySet<DiagnosticFilterId>,
): boolean {
  if (active.size === 0) return true;
  let ok = true;
  if (active.has("critical_only")) {
    ok = ok && isCriticalComponent(row);
  }
  if (active.has("unresolved_only")) {
    ok = ok && isUnresolvedComponent(row);
  }
  if (active.has("live_relevant")) {
    ok = ok && LIVE_RELEVANT.has(row.id);
  }
  if (active.has("data_only")) {
    ok = ok && DATA_IDS.has(row.id);
  }
  if (active.has("broker_auth")) {
    ok = ok && BROKER_AUTH_IDS.has(row.id);
  }
  return ok;
}

export function sortComponentsByBusinessPriority(
  rows: readonly SelfHealingComponentRow[],
): SelfHealingComponentRow[] {
  const rank = (r: SelfHealingComponentRow) => {
    const tier = businessTierForComponentId(r.id);
    const st =
      r.status === "down"
        ? 0
        : r.status === "degraded"
          ? 1
          : r.status === "unknown"
            ? 2
            : r.status === "not_configured"
              ? 3
              : 4;
    return tier * 10 + st;
  };
  return [...rows].sort((a, b) => rank(a) - rank(b));
}

/** Vorfälle ohne 1:1-Doppel zur Komponenten-Tabelle (Alerts, Health-Warnings, Health-Load). */
export function crossCuttingIncidents(
  incidents: readonly SelfHealingIncident[],
): SelfHealingIncident[] {
  return incidents.filter((i) => {
    if (i.id.startsWith("inc:alert:")) return true;
    if (i.id.startsWith("inc:wd:")) return true;
    if (i.id === "inc:health_load") return true;
    return false;
  });
}

export function formatDiagnosticMarkdownReport(args: {
  snap: SelfHealingSnapshot;
  rowLabels: Record<string, string>;
  t: (key: string, vars?: Record<string, string | number>) => string;
}): string {
  const { snap, rowLabels, t } = args;
  const lines: string[] = [];
  lines.push(`# ${t("pages.diagnostics.exportTitle")}`);
  lines.push("");
  lines.push(
    `${t("pages.diagnostics.exportCollected")}: ${new Date(snap.collected_at_ms).toISOString()}`,
  );
  if (snap.support_reference) {
    lines.push(
      `${t("pages.diagnostics.exportSupportRef")}: ${snap.support_reference}`,
    );
  }
  lines.push("");
  const sorted = sortComponentsByBusinessPriority(snap.components);
  for (const tier of [0, 1, 2, 3] as const) {
    const tierRows = sorted.filter((r) => businessTierForComponentId(r.id) === tier);
    if (tierRows.length === 0) continue;
    lines.push(`## ${t("pages.diagnostics.exportTier", { tier: tier + 1 })}`);
    lines.push("");
    for (const r of tierRows) {
      const name = rowLabels[r.id] ?? r.id;
      lines.push(`### ${name}`);
      lines.push(`- **${t("pages.diagnostics.colStatus")}:** ${r.status}`);
      lines.push(
        `- **${t("pages.diagnostics.colChecked")}:** ${new Date(r.lastSeenMs).toISOString()}`,
      );
      lines.push(
        `- **${t("pages.diagnostics.colProblem")}:** ${r.suspectedCause || "—"}`,
      );
      lines.push(
        `- **${t("pages.diagnostics.colImpact")}:** ${r.impact || "—"}`,
      );
      lines.push(
        `- **${t("pages.diagnostics.colAction")}:** ${r.nextStep || "—"}`,
      );
      if (r.manualRemediationRequired) {
        lines.push(`- **${t("pages.diagnostics.exportManual")}**`);
      }
      lines.push("");
    }
  }
  const extra = crossCuttingIncidents(snap.incidents);
  if (extra.length > 0) {
    lines.push(`## ${t("pages.diagnostics.exportExtraIncidents")}`);
    lines.push("");
    for (const i of extra) {
      lines.push(`### ${i.headline}`);
      lines.push(i.suspectedCause);
      lines.push("");
    }
  }
  return lines.join("\n");
}
