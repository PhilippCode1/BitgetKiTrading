import Link from "next/link";

import { consolePath } from "@/lib/console-paths";
import { formatNum, formatTsMs } from "@/lib/format";
import type { StrategyRegistryItem } from "@/lib/types";

type Props = Readonly<{
  items: StrategyRegistryItem[];
  emptyMessage: string;
  detailLinkLabel: string;
  signalPathHeader: string;
  statusLabelNotSet: string;
  thName: string;
  thStatus: string;
  thInstrument: string;
  thVersion: string;
  thPfRoll: string;
  thWinRoll: string;
  mobileListAria: string;
  mobileInstrumentLabel: string;
  mobilePfLabel: string;
  mobileWinLabel: string;
  /** title-Attribut fuer Rolling-Spalten (30d-Join). */
  rollingMetricsThTitle?: string;
  /** Kurzzeile unter PF, wenn Gateway rolling_snapshot_empty meldet. */
  rollingNoSnapshotNote?: string;
}>;

export function StrategiesTable({
  items,
  emptyMessage,
  detailLinkLabel,
  signalPathHeader,
  statusLabelNotSet,
  thName,
  thStatus,
  thInstrument,
  thVersion,
  thPfRoll,
  thWinRoll,
  mobileListAria,
  mobileInstrumentLabel,
  mobilePfLabel,
  mobileWinLabel,
  rollingMetricsThTitle,
  rollingNoSnapshotNote,
}: Props) {
  if (items.length === 0) {
    return <p className="muted">{emptyMessage}</p>;
  }
  return (
    <>
      <ul
        className="console-stack-list console-mobile-only"
        aria-label={mobileListAria}
      >
        {items.map((s) => {
          const pf =
            typeof s.rolling_pf === "number"
              ? s.rolling_pf
              : Number(s.rolling_pf);
          const wr =
            typeof s.rolling_win_rate === "number"
              ? s.rolling_win_rate
              : Number(s.rolling_win_rate);
          const scope = s.scope_json;
          const sigN = s.signal_path_signal_count ?? 0;
          const statusLabel =
            s.status === "not_set" ? statusLabelNotSet : s.status;
          const pfTxt = Number.isFinite(pf) ? formatNum(pf, 2) : "—";
          const wrTxt = Number.isFinite(wr)
            ? wr <= 1
              ? `${formatNum(wr * 100, 1)} %`
              : `${formatNum(wr, 1)} %`
            : "—";
          return (
            <li key={`m-${s.strategy_id}`} className="console-stack-card">
              <div className="console-stack-card__meta">
                <span className="status-pill">{statusLabel}</span>
              </div>
              <p className="console-stack-card__title">{s.name}</p>
              <div className="console-stack-card__dl">
                <div>
                  <span className="console-stack-card__k">
                    {mobileInstrumentLabel}
                  </span>
                  <span className="console-stack-card__v">
                    {scope?.symbol ?? "—"}
                  </span>
                </div>
                <div>
                  <span className="console-stack-card__k">{mobilePfLabel}</span>
                  <span className="console-stack-card__v">{pfTxt}</span>
                </div>
                <div>
                  <span className="console-stack-card__k">
                    {mobileWinLabel}
                  </span>
                  <span className="console-stack-card__v">{wrTxt}</span>
                </div>
                <div>
                  <span className="console-stack-card__k">
                    {signalPathHeader}
                  </span>
                  <span className="console-stack-card__v">{sigN}</span>
                </div>
              </div>
              <div className="signals-mobile-card__actions">
                <Link
                  href={consolePath(`strategies/${s.strategy_id}`)}
                  className="public-btn ghost"
                >
                  {detailLinkLabel}
                </Link>
              </div>
            </li>
          );
        })}
      </ul>
      <div className="table-wrap console-desktop-only">
        <table className="data-table">
          <thead>
            <tr>
              <th>{thName}</th>
              <th>{thStatus}</th>
              <th>{thInstrument}</th>
              <th>{thVersion}</th>
              <th title={rollingMetricsThTitle}>{thPfRoll}</th>
              <th title={rollingMetricsThTitle}>{thWinRoll}</th>
              <th>{signalPathHeader}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((s) => {
              const pf =
                typeof s.rolling_pf === "number"
                  ? s.rolling_pf
                  : Number(s.rolling_pf);
              const wr =
                typeof s.rolling_win_rate === "number"
                  ? s.rolling_win_rate
                  : Number(s.rolling_win_rate);
              const scope = s.scope_json;
              const sigN = s.signal_path_signal_count ?? 0;
              const statusLabel =
                s.status === "not_set" ? statusLabelNotSet : s.status;
              return (
                <tr key={s.strategy_id}>
                  <td>{s.name}</td>
                  <td>
                    <span className="status-pill">{statusLabel}</span>
                  </td>
                  <td>
                    {scope ? (
                      <>
                        <div>{scope.symbol ?? "—"}</div>
                        <div className="mono-small">
                          {scope.market_family ?? "—"}
                          {scope.product_type ? ` / ${scope.product_type}` : ""}
                        </div>
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>{s.latest_version ?? "—"}</td>
                  <td>
                    <div>{Number.isFinite(pf) ? formatNum(pf, 2) : "—"}</div>
                    {s.rolling_snapshot_empty && rollingNoSnapshotNote ? (
                      <div className="muted small">{rollingNoSnapshotNote}</div>
                    ) : null}
                  </td>
                  <td>
                    {Number.isFinite(wr)
                      ? wr <= 1
                        ? `${formatNum(wr * 100, 1)} %`
                        : `${formatNum(wr, 1)} %`
                      : "—"}
                  </td>
                  <td>
                    <div>{sigN}</div>
                    <div className="muted small">
                      {formatTsMs(s.signal_path_last_signal_ts_ms ?? null)}
                    </div>
                  </td>
                  <td>
                    <Link href={consolePath(`strategies/${s.strategy_id}`)}>
                      {detailLinkLabel}
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
