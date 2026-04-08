import type {
  AlertOutboxItem,
  MonitorAlertItem,
  SystemHealthResponse,
} from "@/lib/types";

const SENSITIVE_KEY_RE =
  /password|secret|token|authorization|api_key|apikey|private_key|credential|bearer|jwt|dsn/i;

const MAX_STRING = 800;

function truncateStr(s: string, max: number): string {
  const t = s.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max)}…`;
}

/**
 * Entfernt/ersetzt typische Geheimnis-Felder in Diagnose-Kontext (rekursiv).
 * Wird serverseitig vor Serialisierung an den Client und im BFF erneut angewendet.
 */
export function redactSensitiveDiagnosticBranches(
  value: unknown,
  depth = 0,
): unknown {
  if (depth > 14) return "[DEPTH]";
  if (value === null || typeof value !== "object") {
    if (typeof value === "string") {
      return truncateStr(value, MAX_STRING);
    }
    return value;
  }
  if (Array.isArray(value)) {
    return value
      .slice(0, 80)
      .map((v) => redactSensitiveDiagnosticBranches(v, depth + 1));
  }
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(value)) {
    if (SENSITIVE_KEY_RE.test(k)) {
      out[k] = "[REMOVED]";
      continue;
    }
    out[k] = redactSensitiveDiagnosticBranches(v, depth + 1);
  }
  return out;
}

export function buildSafetyDiagnosticContext(input: {
  health: SystemHealthResponse | null;
  openAlerts: readonly MonitorAlertItem[];
  outbox: readonly AlertOutboxItem[];
  loadError: string | null;
}): Record<string, unknown> {
  const h = input.health;
  const healthSlice = h
    ? {
        server_ts_ms: h.server_ts_ms,
        symbol: h.symbol,
        aggregate: h.aggregate ?? null,
        truth_layer: h.truth_layer ?? null,
        readiness_core: h.readiness_core ?? null,
        execution: h.execution,
        database: h.database,
        database_schema: h.database_schema ?? null,
        data_freshness: h.data_freshness,
        redis: h.redis ?? null,
        services: (h.services ?? []).slice(0, 48).map((s) => ({
          name: s.name,
          status: s.status,
          configured: s.configured,
          ready: s.ready,
          latency_ms: s.latency_ms,
          http_status: s.http_status,
          note: s.note ? truncateStr(s.note, 400) : undefined,
          last_error: s.last_error ? truncateStr(s.last_error, 400) : undefined,
          detail: s.detail ? truncateStr(s.detail, 400) : undefined,
        })),
        ops: h.ops,
        warnings: (h.warnings ?? [])
          .slice(0, 40)
          .map((w) => truncateStr(w, 500)),
        warnings_display: (h.warnings_display ?? h.warningsDisplay ?? [])
          .slice(0, 24)
          .map((w) => ({
            code: w.code,
            title: truncateStr(w.title, 400),
            message: truncateStr(w.message, 600),
            next_step: truncateStr(w.next_step, 400),
            related_services: truncateStr(w.related_services, 400),
          })),
        provider_ops_summary: h.provider_ops_summary ?? null,
        integrations_matrix_present: Boolean(h.integrations_matrix),
      }
    : null;

  const alerts = input.openAlerts.slice(0, 40).map((a) => ({
    alert_key: a.alert_key,
    severity: a.severity,
    title: truncateStr(a.title, 200),
    message: truncateStr(a.message, 800),
    state: a.state,
    created_ts: a.created_ts,
    updated_ts: a.updated_ts,
    details: redactSensitiveDiagnosticBranches(a.details) as Record<
      string,
      unknown
    >,
  }));

  const outbox = input.outbox.slice(0, 30).map((o) => ({
    alert_id: o.alert_id,
    alert_type: o.alert_type,
    severity: o.severity,
    state: o.state,
    symbol: o.symbol,
    attempt_count: o.attempt_count,
    last_error: o.last_error ? truncateStr(o.last_error, 500) : null,
    created_ts: o.created_ts,
    payload: redactSensitiveDiagnosticBranches(o.payload) as Record<
      string,
      unknown
    >,
  }));

  return redactSensitiveDiagnosticBranches({
    context_kind: "safety_diagnostic_v1",
    dashboard_load_error: input.loadError
      ? truncateStr(input.loadError, 800)
      : null,
    system_health: healthSlice,
    monitor_open_alerts: alerts,
    alert_outbox_recent: outbox,
    lineage_note_de:
      "data_lineage ist auf dieser Seite nicht enthalten — bei Bedarf Live-Terminal oder Shadow/Live-Konsole prüfen.",
  }) as Record<string, unknown>;
}
