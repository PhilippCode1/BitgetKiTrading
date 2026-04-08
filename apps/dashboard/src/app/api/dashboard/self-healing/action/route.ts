import { NextResponse } from "next/server";

import {
  buildSelfHealingSnapshot,
  type SelfHealingRawInputs,
} from "@/lib/self-healing";
import {
  fetchAlertOutboxRecent,
  fetchMonitorAlertsOpen,
  fetchSystemHealth,
} from "@/lib/api";
import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import { runGatewayBootstrapProbe } from "@/lib/gateway-bootstrap-probe";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

type ActionBody = Readonly<{
  action?: string;
  /** Optional: Komponenten-ID für Logging / zukünftige gezielte Hooks */
  target_component_id?: string;
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
  ]);
  if (!allowed.has(action)) {
    return NextResponse.json(
      { detail: { code: "UNKNOWN_ACTION", action } },
      { status: 400 },
    );
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

  const raw: SelfHealingRawInputs = {
    collected_at_ms,
    support_reference: null,
    health,
    health_load_error,
    probe,
    open_alerts,
    outbox_items,
  };

  const t = await getServerTranslator();
  const snapshot = buildSelfHealingSnapshot(raw, t);

  return NextResponse.json({
    ok: true,
    action,
    target_component_id: body.target_component_id ?? null,
    /** true wenn der Lauf Daten geholt hat (kein reines No-Op). */
    server_ran_probe: true,
    snapshot,
  });
}
