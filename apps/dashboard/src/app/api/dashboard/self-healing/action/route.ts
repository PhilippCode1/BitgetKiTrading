import { NextResponse } from "next/server";

import {
  buildSelfHealingSnapshot,
  type SelfHealingRawInputs,
} from "@/lib/self-healing";
import {
  fetchAlertOutboxRecent,
  fetchMonitorAlertsOpen,
  fetchSelfHealingStatus,
  fetchSystemHealth,
} from "@/lib/api";
import { fetchGatewayUpstream } from "@/lib/gateway-upstream-fetch";
import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import { runGatewayBootstrapProbe } from "@/lib/gateway-bootstrap-probe";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

type ActionBody = Readonly<{
  action?: string;
  /** Optional: Komponenten-ID für Logging / zukünftige gezielte Hooks */
  target_component_id?: string;
  /** z.B. feature-engine — fuer worker_restart (Prompt 74) */
  service_name?: string;
}>;

/**
 * Serverseitige Reparatur-Hooks: aktuell = frischer Snapshot (Health + Edge erneut abfragen).
 * Gezielte Worker-Neustarts gehören ins Gateway/Orchestrierung — hier nur sichere BFF-Schritte.
 */
export async function POST(req: Request) {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;

  let body: ActionBody = {};
  try {
    body = (await req.json()) as ActionBody;
  } catch {
    return NextResponse.json({ detail: "Invalid JSON." }, { status: 400 });
  }

  const action = body.action ?? "refresh_snapshot";
  const allowed = new Set([
    "refresh_snapshot",
    "refetch_health",
    "reprobe_edge",
    "full_stack_refresh",
    "worker_restart",
  ]);
  if (!allowed.has(action)) {
    return NextResponse.json(
      { detail: { code: "UNKNOWN_ACTION", action } },
      { status: 400 },
    );
  }

  let worker_restart_result: { ok: boolean; detail?: string } | null = null;
  if (action === "worker_restart") {
    const svc = (body.service_name || body.target_component_id || "").trim();
    if (!svc) {
      return NextResponse.json(
        { detail: { code: "SERVICE_NAME_REQUIRED" } },
        { status: 400 },
      );
    }
    const gres = await fetchGatewayUpstream("/v1/ops/self-healing/restart", auth.authorization, {
      method: "POST",
      body: JSON.stringify({ service_name: svc }),
    });
    if (!gres.ok) {
      const tx = (await gres.text()).slice(0, 500);
      worker_restart_result = { ok: false, detail: `HTTP ${gres.status}: ${tx}` };
    } else {
      worker_restart_result = { ok: true };
    }
  }

  const collected_at_ms = Date.now();
  let health = null;
  let health_load_error: string | null = null;
  try {
    health = await fetchSystemHealth();
  } catch (e) {
    health_load_error = e instanceof Error ? e.message : "health_fetch_failed";
  }

  let open_alerts: SelfHealingRawInputs["open_alerts"] = [];
  try {
    open_alerts = (await fetchMonitorAlertsOpen()).items;
  } catch {
    open_alerts = [];
  }

  let outbox_items: SelfHealingRawInputs["outbox_items"] = [];
  try {
    outbox_items = (await fetchAlertOutboxRecent()).items;
  } catch {
    outbox_items = [];
  }

  const probe = await runGatewayBootstrapProbe();

  let self_healing_items = null;
  let self_healing_error: string | null = null;
  try {
    const sh = await fetchSelfHealingStatus();
    self_healing_items = (sh.items || []).map((i) => ({
      service_name: i.service_name,
      health_phase: i.health_phase,
      updated_ts: i.updated_ts ?? null,
      restart_events_ts: i.restart_events_ts,
      timeline: [...(i.timeline ?? [])],
    }));
  } catch (e) {
    self_healing_error = e instanceof Error ? e.message : "self_healing_status_failed";
  }

  const raw: SelfHealingRawInputs = {
    collected_at_ms,
    support_reference: null,
    health,
    health_load_error,
    probe,
    open_alerts,
    outbox_items,
    self_healing_items,
    self_healing_error,
  };

  const t = await getServerTranslator();
  const snapshot = buildSelfHealingSnapshot(raw, t);

  return NextResponse.json({
    ok: true,
    action,
    target_component_id: body.target_component_id ?? null,
    service_name: (body.service_name || "").trim() || null,
    /** true wenn der Lauf Daten geholt hat (kein reines No-Op). */
    server_ran_probe: true,
    worker_restart_result: worker_restart_result,
    snapshot,
  });
}
