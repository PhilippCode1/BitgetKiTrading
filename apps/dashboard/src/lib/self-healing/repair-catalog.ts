import type { SelfHealingRepairAction } from "./schema";

/** Standard-Reparaturpfade (Beschriftung via i18n labelKey). */
export const STANDARD_REPAIR_ACTIONS: readonly SelfHealingRepairAction[] = [
  {
    id: "refetch_health",
    kind: "refetch_health",
    labelKey: "pages.selfHealing.actions.refetchHealth",
  },
  {
    id: "recheck_edge",
    kind: "recheck_connection",
    labelKey: "pages.selfHealing.actions.recheckEdge",
    clientDriven: true,
  },
  {
    id: "edge_json",
    kind: "open_edge_diagnostics",
    labelKey: "pages.selfHealing.actions.edgeJson",
    clientDriven: true,
  },
  {
    id: "reload_region",
    kind: "reload_dashboard_region",
    labelKey: "pages.selfHealing.actions.reloadRegion",
    clientDriven: true,
  },
  {
    id: "open_health",
    kind: "open_health_page",
    labelKey: "pages.selfHealing.actions.openHealth",
    clientDriven: true,
  },
  {
    id: "open_terminal",
    kind: "open_live_terminal",
    labelKey: "pages.selfHealing.actions.openTerminal",
    clientDriven: true,
  },
  {
    id: "open_integrations",
    kind: "open_integrations",
    labelKey: "pages.selfHealing.actions.openIntegrations",
    clientDriven: true,
  },
  {
    id: "stream_hint",
    kind: "client_stream_reconnect_hint",
    labelKey: "pages.selfHealing.actions.streamReconnectHint",
    clientDriven: true,
  },
  {
    id: "operator_config",
    kind: "operator_config_hint",
    labelKey: "pages.selfHealing.actions.operatorConfig",
    clientDriven: true,
  },
] as const;

export function repairsFor(
  kinds: readonly SelfHealingRepairAction["kind"][],
): SelfHealingRepairAction[] {
  const set = new Set(kinds);
  return STANDARD_REPAIR_ACTIONS.filter((a) => set.has(a.kind));
}
