import Link from "next/link";

import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { GatewayReadNotice } from "@/components/console/GatewayReadNotice";
import { Header } from "@/components/layout/Header";
import { fetchLiveBrokerForensicTimeline } from "@/lib/api";
import { prettyJsonLine } from "@/lib/live-broker-console";
import { consolePath } from "@/lib/console-paths";
import {
  diagnosticFromSearchParams,
  type ConsoleSearchParams,
} from "@/lib/console-params";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

type Params = { id: string };

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function valueText(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return String(value);
  }
  return JSON.stringify(value);
}

function renderKeyFacts(
  title: string,
  source: Record<string, unknown> | null,
  keys: string[],
) {
  if (!source) return null;
  return (
    <div className="panel">
      <h2>{title}</h2>
      <ul className="news-list operator-metric-list">
        {keys.map((key) => (
          <li key={key}>
            <code>{key}</code>: <strong>{valueText(source[key])}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

function renderJsonPanel(title: string, data: unknown, open = false) {
  if (
    data === null ||
    data === undefined ||
    (Array.isArray(data) && data.length === 0) ||
    (typeof data === "object" &&
      !Array.isArray(data) &&
      Object.keys(asRecord(data) ?? {}).length === 0)
  ) {
    return null;
  }
  return (
    <details className="panel reasons" open={open}>
      <summary>{title}</summary>
      <pre className="json-mini" style={{ maxHeight: 320 }}>
        {prettyJsonLine(data)}
      </pre>
    </details>
  );
}

export default async function LiveBrokerForensicPage(props: {
  params: Params | Promise<Params>;
  searchParams?: ConsoleSearchParams | Promise<ConsoleSearchParams>;
}) {
  const sp = await Promise.resolve(props.searchParams ?? {});
  const diagnostic = diagnosticFromSearchParams(sp);
  const t = await getServerTranslator();
  const { id } = await Promise.resolve(props.params);
  let data = null as Awaited<
    ReturnType<typeof fetchLiveBrokerForensicTimeline>
  > | null;
  let error: string | null = null;
  try {
    data = await fetchLiveBrokerForensicTimeline(id);
  } catch (err) {
    error = err instanceof Error ? err.message : t("errors.fallbackMessage");
  }

  if (error || !data) {
    return (
      <>
        <Header
          title={t("pages.forensic.title")}
          subtitle={t("pages.forensic.subtitle")}
        />
        {error ? (
          <PanelDataIssue err={error} diagnostic={diagnostic} t={t} />
        ) : (
          <div
            className="console-fetch-notice console-fetch-notice--soft"
            role="status"
          >
            <p className="console-fetch-notice__title">
              {t("pages.forensic.notFoundTitle")}
            </p>
            <p className="muted small">{t("pages.forensic.notFound")}</p>
          </div>
        )}
        <p>
          <Link href={consolePath("live-broker")}>
            ← {t("console.nav.live_broker")}
          </Link>
        </p>
      </>
    );
  }

  const decision = asRecord(data.decision);
  const signal = asRecord(data.signal_context);
  const release = asRecord(data.operator_release);
  const shadow = asRecord(data.shadow_live_assessment);
  const risk = asRecord(data.risk_snapshot);
  const learning = asRecord(data.learning_e2e_record);

  const dash = t("pages.broker.emDash");

  return (
    <>
      <Header
        title={`${t("pages.forensic.title")} ${data.execution_id.slice(0, 12)}…`}
        subtitle={t("pages.forensic.subtitle")}
      />
      <p>
        <Link href={consolePath("live-broker")}>
          ← {t("console.nav.live_broker")}
        </Link>
      </p>

      {data.status === "degraded" ? (
        <div className="panel" role="status">
          <GatewayReadNotice payload={data} t={t} />
        </div>
      ) : null}

      <div className="grid-2">
        {renderKeyFacts(t("pages.forensic.panelExecution"), decision, [
          "decision_action",
          "decision_reason",
          "effective_runtime_mode",
          "requested_runtime_mode",
          "symbol",
          "direction",
          "created_ts",
        ])}
        {renderKeyFacts(t("pages.forensic.panelSignalContext"), signal, [
          "trade_action",
          "decision_state",
          "meta_trade_lane",
          "playbook_id",
          "playbook_family",
          "strategy_name",
          "regime_state",
          "stop_fragility_0_1",
          "stop_executability_0_1",
          "stop_distance_pct",
        ])}
      </div>

      <div className="grid-2">
        {renderKeyFacts(t("pages.forensic.panelRelease"), release, [
          "released_ts",
          "source",
        ])}
        {renderKeyFacts(t("pages.forensic.panelLearning"), learning, [
          "trade_action",
          "meta_trade_lane",
          "paper_trade_id",
          "trade_evaluation_id",
          "updated_ts",
        ])}
      </div>

      <div className="panel">
        <h2>{t("pages.forensic.timelineTitle")}</h2>
        {(data.timeline_sorted ?? []).length === 0 ? (
          <p className="muted degradation-inline">
            {t("pages.forensic.timelineEmpty")}
          </p>
        ) : (
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("pages.forensic.thTimelineTime")}</th>
                  <th>{t("pages.forensic.thTimelineType")}</th>
                  <th>{t("pages.forensic.thTimelineRef")}</th>
                  <th>{t("pages.forensic.thTimelineSummary")}</th>
                </tr>
              </thead>
              <tbody>
                {(data.timeline_sorted ?? []).map((event, idx) => (
                  <tr key={`${event.kind}-${event.ref ?? idx}`}>
                    <td>{event.ts ?? dash}</td>
                    <td>{event.kind}</td>
                    <td className="mono-small">{event.ref ?? dash}</td>
                    <td className="mono-small">
                      {prettyJsonLine(event.summary)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="grid-2">
        {renderJsonPanel("Risk Snapshot", risk)}
        {renderJsonPanel(t("pages.forensic.panelShadow"), shadow)}
      </div>

      <div className="grid-2">
        {renderJsonPanel(t("pages.forensic.panelSignal"), signal, true)}
        {renderJsonPanel(t("pages.forensic.panelLearningE2e"), learning, true)}
      </div>

      <div className="grid-2">
        {renderJsonPanel("Orders", data.orders)}
        {renderJsonPanel("Fills", data.fills)}
      </div>

      <div className="grid-2">
        {renderJsonPanel("Exit Plans", data.exit_plans)}
        {renderJsonPanel("Trade Reviews", data.trade_reviews)}
      </div>

      <div className="grid-2">
        {renderJsonPanel(
          t("pages.forensic.panelTelegram"),
          data.telegram_operator_actions,
        )}
        {renderJsonPanel("Telegram Outbox", data.telegram_alert_outbox)}
      </div>

      <div className="grid-2">
        {renderJsonPanel("Gateway Audit", data.gateway_audit_trails)}
        {renderJsonPanel("Audit Trails", data.audit_trails)}
      </div>

      <div className="grid-2">
        {renderJsonPanel("Journal", data.journal)}
        {renderJsonPanel("Order Actions", data.order_actions)}
      </div>

      <div className="grid-2">
        {renderJsonPanel("Paper Positions", data.paper_positions)}
        {renderJsonPanel(t("pages.forensic.panelDecision"), data.decision)}
      </div>
    </>
  );
}
