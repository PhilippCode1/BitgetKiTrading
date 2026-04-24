import { randomUUID } from "crypto";

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
import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import { runGatewayBootstrapProbe } from "@/lib/gateway-bootstrap-probe";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

async function collectRaw(): Promise<SelfHealingRawInputs> {
  const collected_at_ms = Date.now();
  const support_reference = randomUUID();
  let health = null;
  let health_load_error: string | null = null;
  try {
    health = await fetchSystemHealth();
  } catch (e) {
    health_load_error = e instanceof Error ? e.message : "health_fetch_failed";
  }

  let open_alerts: Awaited<
    ReturnType<typeof fetchMonitorAlertsOpen>
  >["items"] = [];
  try {
    const a = await fetchMonitorAlertsOpen();
    open_alerts = a.items;
  } catch {
    open_alerts = [];
  }

  let outbox_items: Awaited<
    ReturnType<typeof fetchAlertOutboxRecent>
  >["items"] = [];
  try {
    const o = await fetchAlertOutboxRecent();
    outbox_items = o.items;
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

  return {
    collected_at_ms,
    support_reference,
    health,
    health_load_error,
    probe,
    open_alerts,
    outbox_items,
    self_healing_items,
    self_healing_error,
  };
}

export async function GET() {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;

  const t = await getServerTranslator();
  const raw = await collectRaw();
  const snapshot = buildSelfHealingSnapshot(raw, t);
  return NextResponse.json(snapshot);
}
