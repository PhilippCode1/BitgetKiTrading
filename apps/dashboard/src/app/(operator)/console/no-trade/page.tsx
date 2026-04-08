import Link from "next/link";

import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { Header } from "@/components/layout/Header";
import { fetchLearningModelOpsReport, fetchSignalsRecent } from "@/lib/api";
import { consolePath } from "@/lib/console-paths";
import {
  diagnosticFromSearchParams,
  type ConsoleSearchParams,
} from "@/lib/console-params";
import { formatTsMs } from "@/lib/format";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import type { SignalRecentItem } from "@/lib/types";

export const dynamic = "force-dynamic";

function asNoTradeBlock(
  report: Record<string, unknown> | null,
): Record<string, unknown> | null {
  if (!report) return null;
  const raw = report.abstention_and_no_trade;
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    return raw as Record<string, unknown>;
  }
  return null;
}

export default async function NoTradePage({
  searchParams = {},
}: {
  searchParams?: ConsoleSearchParams | Promise<ConsoleSearchParams>;
}) {
  const sp = await Promise.resolve(searchParams);
  const diagnostic = diagnosticFromSearchParams(sp);
  const t = await getServerTranslator();
  let report: Record<string, unknown> | null = null;
  let samples: SignalRecentItem[] = [];
  let err: string | null = null;
  try {
    const [r, sig] = await Promise.all([
      fetchLearningModelOpsReport({ slice_hours: 168 }),
      fetchSignalsRecent({ trade_action: "do_not_trade", limit: 25 }),
    ]);
    report = r;
    samples = sig.items;
  } catch (e) {
    err = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }
  const block = asNoTradeBlock(report);

  return (
    <>
      <Header
        title={t("pages.noTrade.title")}
        subtitle={t("pages.noTrade.subtitle")}
      />
      <p className="muted small">
        {t("pages.noTrade.signalsHint")}{" "}
        <Link href={consolePath("signals")}>{t("console.nav.signals")}</Link>.
      </p>
      <PanelDataIssue err={err} diagnostic={diagnostic} t={t} />
      <div className="panel">
        <h2>{t("pages.noTrade.aggregateTitle")}</h2>
        {!block ? (
          <p className="muted degradation-inline">
            {t("pages.noTrade.aggregateEmpty")}
          </p>
        ) : (
          <ul className="news-list operator-metric-list">
            <li>
              Signale im Fenster:{" "}
              <strong>{String(block.n_signals ?? "—")}</strong>
            </li>
            <li>
              <code>do_not_trade</code>:{" "}
              <strong>{String(block.n_do_not_trade ?? "—")}</strong>
            </li>
            <li>
              Andere <code>trade_action</code>:{" "}
              <strong>{String(block.n_other_trade_action ?? "—")}</strong>
            </li>
            <li>
              OOD-Alert-Anteil (Proxy):{" "}
              <strong>
                {block.abstain_with_ood_alert_fraction == null
                  ? "—"
                  : `${(Number(block.abstain_with_ood_alert_fraction) * 100).toFixed(1)} %`}
              </strong>
            </li>
            {typeof block.note_de === "string" ? (
              <li className="muted small">{block.note_de}</li>
            ) : null}
          </ul>
        )}
      </div>
      <div className="panel">
        <h2>{t("pages.noTrade.sampleTitle")}</h2>
        {samples.length === 0 ? (
          <p className="muted degradation-inline">
            {t("pages.noTrade.tableEmptyLimit")}
          </p>
        ) : (
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("pages.noTrade.thTime")}</th>
                  <th>{t("pages.noTrade.thSymbol")}</th>
                  <th>{t("pages.noTrade.thTf")}</th>
                  <th>{t("pages.noTrade.thPlaybook")}</th>
                  <th>{t("pages.noTrade.thRouter")}</th>
                  <th>{t("pages.noTrade.thDetail")}</th>
                </tr>
              </thead>
              <tbody>
                {samples.map((s) => (
                  <tr key={s.signal_id}>
                    <td>{formatTsMs(s.analysis_ts_ms)}</td>
                    <td>{s.symbol}</td>
                    <td>{s.timeframe}</td>
                    <td className="mono-small">{s.playbook_id ?? "—"}</td>
                    <td className="mono-small">
                      {s.specialist_router_id ?? "—"}
                    </td>
                    <td>
                      <Link
                        href={`${consolePath("signals")}/${encodeURIComponent(s.signal_id)}`}
                      >
                        {t("pages.noTrade.linkSignal")}
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
