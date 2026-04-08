/**
 * Self-Healing-Hub: einheitliches Diagnose- und Reparatur-Modell (Dashboard-BFF + Gateway-Health).
 */

export type SelfHealingSeverity =
  | "info"
  | "hint"
  | "warning"
  | "critical"
  | "blocking";

/** Ampel je Komponente — konsolidiert aus Health-Probes und Edge-Diagnose. */
export type SelfHealingComponentStatus =
  | "ok"
  | "degraded"
  | "down"
  | "unknown"
  | "not_configured";

export type SelfHealingRepairActionKind =
  | "recheck_connection"
  | "refetch_health"
  | "open_edge_diagnostics"
  | "reload_dashboard_region"
  | "open_health_page"
  | "open_live_terminal"
  | "open_integrations"
  | "client_stream_reconnect_hint"
  | "operator_config_hint";

export type SelfHealingRepairAction = Readonly<{
  id: string;
  kind: SelfHealingRepairActionKind;
  /** i18n-Key unter pages.selfHealing.actions.* */
  labelKey: string;
  /** true = nur Hinweis/Link, kein garantierter Server-Side-Effekt */
  clientDriven?: boolean;
}>;

export type SelfHealingComponentRow = Readonly<{
  id: string;
  /** i18n: pages.selfHealing.components.<id> */
  labelKey: string;
  categoryKey: string;
  status: SelfHealingComponentStatus;
  configured: boolean;
  lastSeenMs: number;
  /** Geschätzter Beginn eines Problems (z. B. Alert created_ts) */
  startedAtMs: number | null;
  suspectedCause: string;
  impact: string;
  autoRemediations: readonly string[];
  nextStep: string;
  technicalDetail: string;
  availableRepairs: readonly SelfHealingRepairAction[];
  manualRemediationRequired: boolean;
}>;

export type SelfHealingIncident = Readonly<{
  id: string;
  dedupeKey: string;
  severity: SelfHealingSeverity;
  areaLabelKey: string;
  headline: string;
  startedAtMs: number | null;
  lastSeenMs: number;
  suspectedCause: string;
  technicalDetail: string;
  impact: string;
  autoRemediations: readonly string[];
  nextStep: string;
  manualRemediationRequired: boolean;
  componentId: string | null;
  repairLogKey: string | null;
}>;

export type SelfHealingHealingHint = Readonly<{
  id: string;
  /** i18n pages.selfHealing.healingHints.<id> */
  messageKey: string;
  sinceMs: number | null;
}>;

export type SelfHealingHistoryEntry = Readonly<{
  ts_ms: number;
  kind: "snapshot" | "repair_attempt" | "user_note";
  summary: string;
  detail?: string;
}>;

export type SelfHealingNarrativeFacts = Readonly<{
  aggregateLevel: "green" | "degraded" | "red" | null;
  healthyCount: number;
  degradedCount: number;
  downCount: number;
  notConfiguredCount: number;
  openIncidentCount: number;
  edgeBlocksReads: boolean;
  worstComponentIds: readonly string[];
}>;

export type SelfHealingSnapshot = Readonly<{
  schema_version: 1;
  collected_at_ms: number;
  support_reference: string | null;
  health_load_error: string | null;
  edge_root_cause: string;
  edge_blocks_v1_reads: boolean;
  components: readonly SelfHealingComponentRow[];
  incidents: readonly SelfHealingIncident[];
  healing_hints: readonly SelfHealingHealingHint[];
  not_auto_fixable: readonly SelfHealingIncident[];
  narrative_facts: SelfHealingNarrativeFacts;
}>;
