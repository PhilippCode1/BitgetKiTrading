import Link from "next/link";

import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { EmptyStateHelp } from "@/components/help/EmptyStateHelp";
import { Header } from "@/components/layout/Header";
import { fetchAlertOutboxRecent, fetchLiveBrokerDecisions } from "@/lib/api";
import { consolePath } from "@/lib/console-paths";
import {
  diagnosticFromSearchParams,
  type ConsoleSearchParams,
} from "@/lib/console-params";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import {
  buildDecisionBuckets,
  matchAlertToDecision,
} from "@/lib/operator-console";

export const dynamic = "force-dynamic";

export default async function ApprovalsPage({
  searchParams = {},
}: {
  searchParams?: ConsoleSearchParams | Promise<ConsoleSearchParams>;
}) {
  const sp = await Promise.resolve(searchParams);
  const diagnostic = diagnosticFromSearchParams(sp);
  const t = await getServerTranslator();
  let decisions: import("@/lib/types").LiveBrokerDecisionItem[] = [];
  let outbox: import("@/lib/types").AlertOutboxItem[] = [];
  let err: string | null = null;
  try {
    const [d, o] = await Promise.all([
      fetchLiveBrokerDecisions(),
      fetchAlertOutboxRecent(),
    ]);
    decisions = d.items;
    outbox = o.items;
  } catch (e) {
    err = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  const buckets = buildDecisionBuckets(decisions);
  const approvalQueue = buckets.approvalQueue.map((decision) => ({
    decision,
    alert: matchAlertToDecision(decision, outbox),
  }));

  return (
    <>
      <Header title={t("approvals.title")} subtitle={t("approvals.subtitle")} />
      <p className="muted small">
        {t("approvals.contextHint")}{" "}
        <Link href={consolePath("ops")}>{t("console.nav.ops")}</Link>.
      </p>
      <PanelDataIssue err={err} diagnostic={diagnostic} t={t} />
      <div className="panel">
        <h2>{t("approvals.openApprovals")}</h2>
        {approvalQueue.length === 0 ? (
          <EmptyStateHelp
            titleKey="help.approvals.emptyTitle"
            bodyKey="help.approvals.emptyBody"
            stepKeys={[
              "help.approvals.step1",
              "help.approvals.step2",
              "help.approvals.step3",
            ]}
          />
        ) : (
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("approvals.thSymbol")}</th>
                  <th>{t("approvals.thFamily")}</th>
                  <th>{t("approvals.thLane")}</th>
                  <th>{t("approvals.thAction")}</th>
                  <th>{t("approvals.thMirror")}</th>
                  <th>{t("approvals.thTelegram")}</th>
                  <th>{t("approvals.thForensic")}</th>
                </tr>
              </thead>
              <tbody>
                {approvalQueue.map(({ decision, alert }) => (
                  <tr key={decision.execution_id}>
                    <td>{decision.symbol}</td>
                    <td className="mono-small">
                      {decision.signal_market_family ?? "—"}
                    </td>
                    <td className="mono-small">
                      {decision.signal_meta_trade_lane ?? "—"}
                    </td>
                    <td className="mono-small">{decision.decision_action}</td>
                    <td>
                      {decision.live_mirror_eligible == null
                        ? "—"
                        : `${String(decision.live_mirror_eligible)} / match ${String(decision.shadow_live_match_ok ?? "—")}`}
                    </td>
                    <td className="mono-small">
                      {alert
                        ? `${alert.alert_type} / ${alert.state} / ${alert.telegram_message_id ?? "—"}`
                        : "—"}
                    </td>
                    <td>
                      <Link
                        href={`${consolePath("live-broker")}/forensic/${decision.execution_id}`}
                      >
                        {t("approvals.forensicLink")}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
