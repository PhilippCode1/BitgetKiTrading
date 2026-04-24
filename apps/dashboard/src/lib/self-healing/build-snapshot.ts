import type { GatewayBootstrapProbeResult } from "@/lib/gateway-bootstrap-probe";
import type {
  AlertOutboxItem,
  DatabaseSchemaHealthDetail,
  IntegrationsMatrixRow,
  MonitorAlertItem,
  SystemHealthResponse,
  SystemHealthServiceItem,
} from "@/lib/types";

import { SELF_HEALING_REGISTRY } from "./registry";
import { repairsFor } from "./repair-catalog";
import type {
  SelfHealingComponentRow,
  SelfHealingComponentStatus,
  SelfHealingHealingHint,
  SelfHealingIncident,
  SelfHealingNarrativeFacts,
  SelfHealingSeverity,
  SelfHealingSnapshot,
  SelfHealingStateItem,
} from "./schema";

export type SelfHealingTranslate = (
  key: string,
  vars?: Record<string, string | number | boolean>,
) => string;

export type SelfHealingRawInputs = Readonly<{
  collected_at_ms: number;
  support_reference: string | null;
  health: SystemHealthResponse | null;
  health_load_error: string | null;
  probe: GatewayBootstrapProbeResult;
  open_alerts: readonly MonitorAlertItem[];
  outbox_items: readonly AlertOutboxItem[];
  self_healing_items: readonly SelfHealingStateItem[] | null;
  self_healing_error: string | null;
}>;

function serviceByName(
  health: SystemHealthResponse | null,
  name: string,
): SystemHealthServiceItem | null {
  if (!health?.services?.length) return null;
  return health.services.find((s) => s.name === name) ?? null;
}

function mapProbeServiceStatus(st: string | undefined): SelfHealingComponentStatus {
  const s = (st || "").toLowerCase();
  if (s === "ok") return "ok";
  if (s === "degraded") return "degraded";
  if (s === "error" || s === "down") return "down";
  if (s === "not_configured") return "not_configured";
  return "unknown";
}

function severityFromComponent(
  st: SelfHealingComponentStatus,
  manual: boolean,
): SelfHealingSeverity {
  if (st === "down") return manual ? "blocking" : "critical";
  if (st === "degraded") return "warning";
  if (st === "not_configured") return "hint";
  if (st === "unknown") return "hint";
  return "info";
}

function technicalJson(obj: unknown): string {
  try {
    return JSON.stringify(obj, null, 2);
  } catch {
    return String(obj);
  }
}

function worstIntegrationRow(
  health: SystemHealthResponse | null,
): IntegrationsMatrixRow | null {
  const rows = health?.integrations_matrix?.integrations;
  if (!rows?.length) return null;
  const rank = (h: string) => {
    const x = h.toLowerCase();
    if (x === "error" || x === "down") return 3;
    if (x === "degraded") return 2;
    if (x === "unknown") return 1;
    return 0;
  };
  let best: IntegrationsMatrixRow | null = null;
  let bestR = -1;
  for (const r of rows) {
    const rr = rank(r.health_status);
    if (rr > bestR) {
      bestR = rr;
      best = r;
    }
  }
  return bestR > 0 ? best : null;
}

export function buildSelfHealingSnapshot(
  input: SelfHealingRawInputs,
  t: SelfHealingTranslate,
): SelfHealingSnapshot {
  const { collected_at_ms, support_reference, health, health_load_error, probe } =
    input;
  const blocks = probe.blocksV1Reads;

  const components: SelfHealingComponentRow[] = [];
  const incidents: SelfHealingIncident[] = [];

  const pushIncident = (inc: SelfHealingIncident) => {
    incidents.push(inc);
  };

  for (const def of SELF_HEALING_REGISTRY) {
    const compName = t(`pages.selfHealing.components.${def.id}.name`);
    let status: SelfHealingComponentStatus = "unknown";
    let configured = true;
    let suspected = "";
    let technical: Record<string, unknown> = {};
    let manual = false;
    const lastSeen = collected_at_ms;

    switch (def.id) {
      case "gateway_edge": {
        status = probe.rootCause === "ok" ? "ok" : "down";
        suspected =
          probe.rootCause === "ok"
            ? t("pages.selfHealing.causes.edgeOk")
            : t("pages.selfHealing.causes.edgeIssue", {
                cause: probe.detail.slice(0, 220),
              });
        technical = {
          rootCause: probe.rootCause,
          blocksV1Reads: probe.blocksV1Reads,
          gatewayHealthHttpStatus: probe.gatewayHealthHttpStatus,
        };
        manual =
          probe.rootCause === "api_gateway_url_missing" ||
          probe.rootCause === "dashboard_authorization_missing";
        break;
      }
      case "dashboard_bff": {
        status = blocks ? "degraded" : "ok";
        suspected = blocks
          ? t("pages.selfHealing.causes.bffBlocked")
          : t("pages.selfHealing.causes.bffOk");
        technical = { blocksV1Reads: blocks };
        break;
      }
      case "api_gateway": {
        const svc = serviceByName(health, "api-gateway");
        if (!svc) {
          status = health ? "unknown" : "unknown";
          suspected = t("pages.selfHealing.causes.noHealthPayload");
        } else {
          configured = svc.configured !== false;
          status = mapProbeServiceStatus(svc.status);
          suspected =
            (svc.note && String(svc.note)) ||
            (svc.detail && String(svc.detail)) ||
            t("pages.selfHealing.causes.probeStatus", { status: svc.status });
          technical = { ...svc };
        }
        break;
      }
      case "readiness_core": {
        const rc = health?.readiness_core;
        if (!rc) {
          status = health ? "unknown" : "unknown";
          suspected = t("pages.selfHealing.causes.readinessMissing");
        } else {
          status = rc.ok ? "ok" : "down";
          suspected = rc.note
            ? String(rc.note)
            : t("pages.selfHealing.causes.readinessFlag", { ok: rc.ok });
          technical = { ...rc };
        }
        break;
      }
      case "gateway_ready": {
        if (probe.gatewayReadyFlag === true) status = "ok";
        else if (probe.gatewayReadyFlag === false) status = "degraded";
        else status = "unknown";
        suspected =
          probe.gatewayReadySummary ||
          t("pages.selfHealing.causes.readyUnknown", {
            flag: String(probe.gatewayReadyFlag),
          });
        technical = {
          gatewayReadyFlag: probe.gatewayReadyFlag,
          gatewayReadySummary: probe.gatewayReadySummary,
        };
        manual = probe.gatewayReadyFlag === false;
        break;
      }
      case "gateway_health_http": {
        const st = probe.gatewayHealthHttpStatus;
        if (st == null) {
          status = "down";
          suspected = t("pages.selfHealing.causes.noGatewayHealth");
        } else if (st >= 200 && st < 300) {
          status = "ok";
          suspected = t("pages.selfHealing.causes.httpOk", { code: st });
        } else {
          status = "degraded";
          suspected = t("pages.selfHealing.causes.httpBad", { code: st });
        }
        technical = { gatewayHealthHttpStatus: st };
        break;
      }
      case "operator_jwt_auth": {
        const rc = probe.rootCause;
        if (rc === "ok") {
          status = "ok";
          suspected = t("pages.selfHealing.causes.jwtOk");
        } else if (
          rc === "operator_jwt_unauthorized" ||
          rc === "operator_jwt_forbidden"
        ) {
          status = "down";
          manual = true;
          suspected = t("pages.selfHealing.causes.jwtBad", {
            code: probe.operatorGatewayAuthCode ?? "",
          });
        } else if (blocks) {
          status = "degraded";
          suspected = t("pages.selfHealing.causes.jwtBlocked");
        } else {
          status = "unknown";
          suspected = t("pages.selfHealing.causes.jwtUnknown");
        }
        technical = {
          rootCause: rc,
          operatorHealthHttpStatus: probe.operatorHealthHttpStatus,
          operatorGatewayAuthCode: probe.operatorGatewayAuthCode,
        };
        break;
      }
      case "postgres": {
        const db = health?.database;
        if (!health) {
          status = "unknown";
          suspected = t("pages.selfHealing.causes.noHealth");
        } else if (db === "ok") {
          status = "ok";
          suspected = t("pages.selfHealing.causes.dbOk");
        } else {
          status = "down";
          suspected = t("pages.selfHealing.causes.dbBad", { db: db ?? "?" });
        }
        technical = { database: db, schema: health?.database_schema ?? null };
        manual = db !== "ok" && Boolean(health);
        break;
      }
      case "redis": {
        const r = health?.redis;
        if (!health) {
          status = "unknown";
          suspected = t("pages.selfHealing.causes.noHealth");
        } else if (r === "ok" || r === "skipped") {
          status = r === "ok" ? "ok" : "not_configured";
          suspected =
            r === "ok"
              ? t("pages.selfHealing.causes.redisOk")
              : t("pages.selfHealing.causes.redisSkipped");
        } else {
          status = "degraded";
          suspected = t("pages.selfHealing.causes.redisBad", { redis: r ?? "?" });
        }
        technical = {
          redis: r,
          streams_sample: health?.stream_lengths_top?.slice(0, 5) ?? [],
        };
        break;
      }
      case "migrations": {
        const sch = health?.database_schema as DatabaseSchemaHealthDetail | null;
        if (!sch) {
          status = health ? "unknown" : "unknown";
          suspected = t("pages.selfHealing.causes.migrationUnknown");
        } else if (sch.migrations_fully_applied === true) {
          status = "ok";
          suspected = t("pages.selfHealing.causes.migrationOk");
        } else if (
          (sch.pending_migrations?.length ?? 0) > 0 ||
          sch.migrations_fully_applied === false
        ) {
          status = "degraded";
          manual = true;
          suspected = t("pages.selfHealing.causes.migrationPending", {
            n: sch.pending_migrations?.length ?? 0,
          });
        } else {
          status = "ok";
          suspected = t("pages.selfHealing.causes.migrationOk");
        }
        technical = { ...sch };
        break;
      }
      case "eventbus_streams": {
        const top = health?.stream_lengths_top ?? [];
        const errs = top.filter((x) => x.error);
        const redisBad = health?.redis && health.redis !== "ok";
        if (!health) {
          status = "unknown";
          suspected = t("pages.selfHealing.causes.noHealth");
        } else if (errs.length > 0 || redisBad) {
          status = "degraded";
          suspected = t("pages.selfHealing.causes.streamsIssue", {
            n: errs.length,
          });
        } else {
          status = "ok";
          suspected = t("pages.selfHealing.causes.streamsOk");
        }
        technical = { stream_lengths_top: top.slice(0, 8) };
        break;
      }
      case "data_freshness_candles": {
        const w = health?.warnings ?? [];
        const bad =
          w.some((x) => /stale_candles|no_candles/i.test(x)) ||
          w.some((x) => /candle/i.test(x) && /stale|no_/i.test(x));
        if (!health) status = "unknown";
        else if (bad) {
          status = "degraded";
          suspected = t("pages.selfHealing.causes.freshnessCandles");
        } else {
          status = "ok";
          suspected = t("pages.selfHealing.causes.freshnessCandlesOk");
        }
        technical = {
          last_candle_ts_ms: health?.data_freshness?.last_candle_ts_ms ?? null,
        };
        break;
      }
      case "data_freshness_signals": {
        const w = health?.warnings ?? [];
        const bad = w.some((x) => /stale_signals|no_signals/i.test(x));
        if (!health) status = "unknown";
        else if (bad) {
          status = "degraded";
          suspected = t("pages.selfHealing.causes.freshnessSignals");
        } else {
          status = "ok";
          suspected = t("pages.selfHealing.causes.freshnessSignalsOk");
        }
        technical = {
          last_signal_ts_ms: health?.data_freshness?.last_signal_ts_ms ?? null,
        };
        break;
      }
      case "data_freshness_news": {
        const w = health?.warnings ?? [];
        const bad = w.some((x) => /stale_news|no_news/i.test(x));
        if (!health) status = "unknown";
        else if (bad) {
          status = "degraded";
          suspected = t("pages.selfHealing.causes.freshnessNews");
        } else {
          status = "ok";
          suspected = t("pages.selfHealing.causes.freshnessNewsOk");
        }
        technical = {
          last_news_ts_ms: health?.data_freshness?.last_news_ts_ms ?? null,
        };
        break;
      }
      case "monitor_open_alerts": {
        const n = health?.ops?.monitor?.open_alert_count ?? input.open_alerts.length;
        if (!health && input.open_alerts.length === 0) {
          status = "unknown";
          suspected = t("pages.selfHealing.causes.alertsUnknown");
        } else if (n > 0) {
          status = "degraded";
          suspected = t("pages.selfHealing.causes.openAlerts", { n });
        } else {
          status = "ok";
          suspected = t("pages.selfHealing.causes.noOpenAlerts");
        }
        technical = {
          open_alert_count: n,
          sample: input.open_alerts.slice(0, 3).map((a) => a.alert_key),
        };
        break;
      }
      case "alert_outbox": {
        const pending = health?.ops?.alert_engine?.outbox_pending ?? 0;
        const failed = health?.ops?.alert_engine?.outbox_failed ?? 0;
        if (!health) {
          status = "unknown";
          suspected = t("pages.selfHealing.causes.outboxUnknown");
        } else if (failed > 0) {
          status = "down";
          manual = true;
          suspected = t("pages.selfHealing.causes.outboxFailed", { failed });
        } else if (pending > 50) {
          status = "degraded";
          suspected = t("pages.selfHealing.causes.outboxBacklog", { pending });
        } else {
          status = "ok";
          suspected = t("pages.selfHealing.causes.outboxOk");
        }
        technical = { pending, failed };
        break;
      }
      case "live_reconcile": {
        const lb = health?.ops?.live_broker;
        const st = lb?.latest_reconcile_status?.toLowerCase() ?? "";
        if (!health || !lb) {
          status = "unknown";
          suspected = t("pages.selfHealing.causes.reconcileUnknown");
        } else if (st && st !== "ok" && st !== "matched") {
          status = "degraded";
          suspected = t("pages.selfHealing.causes.reconcileBad", {
            status: lb.latest_reconcile_status ?? "?",
          });
          manual = st.includes("error") || st.includes("fail");
        } else {
          status = "ok";
          suspected = t("pages.selfHealing.causes.reconcileOk");
        }
        technical = { live_broker: lb };
        break;
      }
      case "external_integrations": {
        const row = worstIntegrationRow(health);
        if (!health?.integrations_matrix) {
          status = "not_configured";
          suspected = t("pages.selfHealing.causes.integrationsMissing");
          configured = false;
        } else if (!row) {
          status = "ok";
          suspected = t("pages.selfHealing.causes.integrationsOk");
        } else {
          status = mapProbeServiceStatus(row.health_status);
          suspected =
            row.health_error_public ||
            row.integration_key ||
            t("pages.selfHealing.causes.integrationRow");
          technical = { row };
          manual = status === "down" || status === "degraded";
        }
        break;
      }
      case "provider_ops": {
        const po = health?.provider_ops_summary;
        if (!po || typeof po !== "object" || Array.isArray(po)) {
          status = health ? "ok" : "unknown";
          suspected = health
            ? t("pages.selfHealing.causes.providerOpsAbsent")
            : t("pages.selfHealing.causes.noHealth");
        } else {
          const blob = JSON.stringify(po);
          const looksBad = /error|fail|down|degraded/i.test(blob);
          status = looksBad ? "degraded" : "ok";
          suspected = looksBad
            ? t("pages.selfHealing.causes.providerOpsIssue")
            : t("pages.selfHealing.causes.providerOpsOk");
          technical = { ...po };
        }
        break;
      }
      default: {
        const hn = def.healthServiceName;
        if (!hn) {
          status = "unknown";
          suspected = t("pages.selfHealing.causes.unmapped");
          break;
        }
        const svc = serviceByName(health, hn);
        if (!svc) {
          status = health ? "unknown" : "unknown";
          suspected = t("pages.selfHealing.causes.serviceMissing", {
            name: hn,
          });
        } else {
          configured = svc.configured !== false;
          status = svc.configured === false ? "not_configured" : mapProbeServiceStatus(svc.status);
          const bits = [
            svc.detail,
            svc.note,
            svc.last_error,
            svc.failed_checks?.join(", "),
          ]
            .filter(Boolean)
            .join(" · ");
          suspected =
            bits || t("pages.selfHealing.causes.probeStatus", { status: svc.status });
          technical = { ...svc };
          manual = svc.configured === false;
        }
      }
    }

    const impact =
      status === "ok"
        ? t("pages.selfHealing.impact.ok", { name: compName })
        : status === "not_configured"
          ? t("pages.selfHealing.impact.notConfigured", { name: compName })
          : t("pages.selfHealing.impact.bad", { name: compName });

    const autoRemediations =
      status === "ok"
        ? [t("pages.selfHealing.auto.poll"), t("pages.selfHealing.auto.degradeSafe")]
        : [
            t("pages.selfHealing.auto.retryProbe"),
            t("pages.selfHealing.auto.partialData"),
          ];

    const nextStep =
      manual
        ? t("pages.selfHealing.next.operator")
        : status === "ok"
          ? t("pages.selfHealing.next.none")
          : t("pages.selfHealing.next.retry");

    let availableRepairs = repairsFor([
      "refetch_health",
      "recheck_connection",
      "open_edge_diagnostics",
      "reload_dashboard_region",
      "open_health_page",
    ]);
    if (def.id === "market_stream" || def.id === "live_broker") {
      availableRepairs = [
        ...availableRepairs,
        ...repairsFor([
          "open_live_terminal",
          "client_stream_reconnect_hint",
        ]),
      ];
    }
    if (def.id === "external_integrations" || def.id === "operator_jwt_auth") {
      availableRepairs = [
        ...availableRepairs,
        ...repairsFor(["open_integrations", "operator_config_hint"]),
      ];
    }

    const row: SelfHealingComponentRow = {
      id: def.id,
      labelKey: `pages.selfHealing.components.${def.id}.name`,
      categoryKey: def.categoryKey,
      status,
      configured,
      lastSeenMs: lastSeen,
      startedAtMs: null,
      suspectedCause: suspected,
      impact,
      autoRemediations,
      nextStep,
      technicalDetail: technicalJson(technical),
      availableRepairs,
      manualRemediationRequired: manual || status === "not_configured",
    };
    components.push(row);

    if (status !== "ok") {
      const sev = severityFromComponent(status, manual);
      pushIncident({
        id: `inc:${def.id}:${status}`,
        dedupeKey: `${def.id}:${status}:${suspected.slice(0, 80)}`,
        severity: sev,
        areaLabelKey: def.categoryKey,
        headline: t("pages.selfHealing.incident.headline", {
          name: compName,
          status,
        }),
        startedAtMs: null,
        lastSeenMs: lastSeen,
        suspectedCause: suspected,
        technicalDetail: technicalJson(technical),
        impact,
        autoRemediations,
        nextStep,
        manualRemediationRequired: manual || status === "not_configured",
        componentId: def.id,
        repairLogKey: `repair:${def.id}`,
      });
    }
  }

  for (const a of input.open_alerts) {
    const created = a.created_ts ? Date.parse(a.created_ts) : NaN;
    pushIncident({
      id: `inc:alert:${a.alert_key}`,
      dedupeKey: `monitor:${a.alert_key}`,
      severity: /critical|severe/i.test(a.severity) ? "critical" : "warning",
      areaLabelKey: "pages.selfHealing.categories.operations",
      headline: a.title || a.alert_key,
      startedAtMs: Number.isFinite(created) ? created : null,
      lastSeenMs: collected_at_ms,
      suspectedCause: a.message || t("pages.selfHealing.causes.monitorAlert"),
      technicalDetail: technicalJson(a.details),
      impact: t("pages.selfHealing.impact.monitorAlert"),
      autoRemediations: [
        t("pages.selfHealing.auto.alertCorrelation"),
        t("pages.selfHealing.auto.retryProbe"),
      ],
      nextStep: t("pages.selfHealing.next.ackAlert"),
      manualRemediationRequired: true,
      componentId: "monitor_open_alerts",
      repairLogKey: `alert:${a.alert_key}`,
    });
  }

  const wd = health?.warnings_display ?? health?.warningsDisplay;
  if (wd?.length) {
    for (const w of wd) {
      pushIncident({
        id: `inc:wd:${w.code}`,
        dedupeKey: `wd:${w.code}`,
        severity: "warning",
        areaLabelKey: "pages.selfHealing.categories.platform",
        headline: w.title,
        startedAtMs: null,
        lastSeenMs: collected_at_ms,
        suspectedCause: w.message,
        technicalDetail: technicalJson(w.machine ?? w),
        impact: w.message,
        autoRemediations: [t("pages.selfHealing.auto.followWarning")],
        nextStep: w.next_step || t("pages.selfHealing.next.retry"),
        manualRemediationRequired: true,
        componentId: null,
        repairLogKey: `wd:${w.code}`,
      });
    }
  }

  if (health_load_error) {
    pushIncident({
      id: "inc:health_load",
      dedupeKey: "health:load_error",
      severity: "blocking",
      areaLabelKey: "pages.selfHealing.categories.platform",
      headline: t("pages.selfHealing.incident.healthLoadHeadline"),
      startedAtMs: null,
      lastSeenMs: collected_at_ms,
      suspectedCause: health_load_error,
      technicalDetail: JSON.stringify({ health_load_error }, null, 2),
      impact: t("pages.selfHealing.impact.healthLoad"),
      autoRemediations: [t("pages.selfHealing.auto.retryProbe")],
      nextStep: t("pages.selfHealing.next.edgeAndStack"),
      manualRemediationRequired: false,
      componentId: "api_gateway",
      repairLogKey: "health:load",
    });
  }

  const deduped: SelfHealingIncident[] = [];
  const seen = new Set<string>();
  for (const i of incidents) {
    if (seen.has(i.dedupeKey)) continue;
    seen.add(i.dedupeKey);
    deduped.push(i);
  }
  deduped.sort((a, b) => {
    const rank = (s: SelfHealingSeverity) =>
      ({ blocking: 5, critical: 4, warning: 3, hint: 2, info: 1 }[s] ?? 0);
    return rank(b.severity) - rank(a.severity);
  });

  const healing_hints: SelfHealingHealingHint[] = [
    {
      id: "poll",
      messageKey: "pages.selfHealing.healingHints.poll",
      sinceMs: collected_at_ms,
    },
    {
      id: "bff",
      messageKey: "pages.selfHealing.healingHints.bff",
      sinceMs: collected_at_ms,
    },
    {
      id: "safe_degrade",
      messageKey: "pages.selfHealing.healingHints.safeDegrade",
      sinceMs: collected_at_ms,
    },
  ];
  if (!blocks && health) {
    healing_hints.push({
      id: "paths_ok",
      messageKey: "pages.selfHealing.healingHints.pathsOk",
      sinceMs: collected_at_ms,
    });
  }

  const not_auto_fixable = deduped.filter((i) => i.manualRemediationRequired);

  const healthyCount = components.filter((c) => c.status === "ok").length;
  const degradedCount = components.filter((c) => c.status === "degraded").length;
  const downCount = components.filter((c) => c.status === "down").length;
  const notConfiguredCount = components.filter(
    (c) => c.status === "not_configured",
  ).length;

  const worstComponentIds = components
    .filter((c) => c.status === "down" || c.status === "degraded")
    .slice(0, 5)
    .map((c) => c.id);

  const narrative_facts: SelfHealingNarrativeFacts = {
    aggregateLevel: health?.aggregate?.level ?? null,
    healthyCount,
    degradedCount,
    downCount,
    notConfiguredCount,
    openIncidentCount: deduped.length,
    edgeBlocksReads: blocks,
    worstComponentIds,
  };

  return {
    schema_version: 1,
    collected_at_ms,
    support_reference,
    health_load_error,
    edge_root_cause: probe.rootCause,
    edge_blocks_v1_reads: blocks,
    components,
    incidents: deduped,
    healing_hints,
    not_auto_fixable,
    narrative_facts,
    self_healing_items: input.self_healing_items,
    self_healing_error: input.self_healing_error,
  };
}
