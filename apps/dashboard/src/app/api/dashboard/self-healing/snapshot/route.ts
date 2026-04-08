import { randomUUID } from "crypto";

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

  return {
    collected_at_ms,
    support_reference,
    health,
    health_load_error,
    probe,
    open_alerts,
    outbox_items,
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
