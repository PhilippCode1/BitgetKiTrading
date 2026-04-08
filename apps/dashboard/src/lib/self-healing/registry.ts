/**
 * Vollständige Komponentenliste für den Self-Healing-Hub.
 * Namen sind an api_gateway.routes_system_health._service_definitions angelehnt; ergänzt um
 * Plattform-Schichten (BFF, Postgres, Redis, Migrationen, Integrationen, Reconcile, …).
 */
export type SelfHealingRegistryEntry = Readonly<{
  id: string;
  /** Optional: Name in GET /v1/system/health → services[].name */
  healthServiceName: string | null;
  categoryKey: string;
}>;

export const SELF_HEALING_REGISTRY: readonly SelfHealingRegistryEntry[] = [
  {
    id: "gateway_edge",
    healthServiceName: null,
    categoryKey: "pages.selfHealing.categories.platform",
  },
  {
    id: "dashboard_bff",
    healthServiceName: null,
    categoryKey: "pages.selfHealing.categories.platform",
  },
  {
    id: "api_gateway",
    healthServiceName: "api-gateway",
    categoryKey: "pages.selfHealing.categories.platform",
  },
  {
    id: "readiness_core",
    healthServiceName: null,
    categoryKey: "pages.selfHealing.categories.platform",
  },
  {
    id: "gateway_ready",
    healthServiceName: null,
    categoryKey: "pages.selfHealing.categories.platform",
  },
  {
    id: "gateway_health_http",
    healthServiceName: null,
    categoryKey: "pages.selfHealing.categories.platform",
  },
  {
    id: "operator_jwt_auth",
    healthServiceName: null,
    categoryKey: "pages.selfHealing.categories.security",
  },
  {
    id: "postgres",
    healthServiceName: null,
    categoryKey: "pages.selfHealing.categories.datastores",
  },
  {
    id: "redis",
    healthServiceName: null,
    categoryKey: "pages.selfHealing.categories.datastores",
  },
  {
    id: "migrations",
    healthServiceName: null,
    categoryKey: "pages.selfHealing.categories.datastores",
  },
  {
    id: "eventbus_streams",
    healthServiceName: null,
    categoryKey: "pages.selfHealing.categories.messaging",
  },
  {
    id: "data_freshness_candles",
    healthServiceName: null,
    categoryKey: "pages.selfHealing.categories.freshness",
  },
  {
    id: "data_freshness_signals",
    healthServiceName: null,
    categoryKey: "pages.selfHealing.categories.freshness",
  },
  {
    id: "data_freshness_news",
    healthServiceName: null,
    categoryKey: "pages.selfHealing.categories.freshness",
  },
  {
    id: "market_stream",
    healthServiceName: "market-stream",
    categoryKey: "pages.selfHealing.categories.engines",
  },
  {
    id: "feature_engine",
    healthServiceName: "feature-engine",
    categoryKey: "pages.selfHealing.categories.engines",
  },
  {
    id: "structure_engine",
    healthServiceName: "structure-engine",
    categoryKey: "pages.selfHealing.categories.engines",
  },
  {
    id: "signal_engine",
    healthServiceName: "signal-engine",
    categoryKey: "pages.selfHealing.categories.engines",
  },
  {
    id: "drawing_engine",
    healthServiceName: "drawing-engine",
    categoryKey: "pages.selfHealing.categories.engines",
  },
  {
    id: "news_engine",
    healthServiceName: "news-engine",
    categoryKey: "pages.selfHealing.categories.engines",
  },
  {
    id: "llm_orchestrator",
    healthServiceName: "llm-orchestrator",
    categoryKey: "pages.selfHealing.categories.engines",
  },
  {
    id: "paper_broker",
    healthServiceName: "paper-broker",
    categoryKey: "pages.selfHealing.categories.execution",
  },
  {
    id: "live_broker",
    healthServiceName: "live-broker",
    categoryKey: "pages.selfHealing.categories.execution",
  },
  {
    id: "learning_engine",
    healthServiceName: "learning-engine",
    categoryKey: "pages.selfHealing.categories.engines",
  },
  {
    id: "alert_engine",
    healthServiceName: "alert-engine",
    categoryKey: "pages.selfHealing.categories.operations",
  },
  {
    id: "monitor_engine",
    healthServiceName: "monitor-engine",
    categoryKey: "pages.selfHealing.categories.operations",
  },
  {
    id: "monitor_open_alerts",
    healthServiceName: null,
    categoryKey: "pages.selfHealing.categories.operations",
  },
  {
    id: "alert_outbox",
    healthServiceName: null,
    categoryKey: "pages.selfHealing.categories.operations",
  },
  {
    id: "live_reconcile",
    healthServiceName: null,
    categoryKey: "pages.selfHealing.categories.execution",
  },
  {
    id: "external_integrations",
    healthServiceName: null,
    categoryKey: "pages.selfHealing.categories.external",
  },
  {
    id: "provider_ops",
    healthServiceName: null,
    categoryKey: "pages.selfHealing.categories.external",
  },
] as const;
