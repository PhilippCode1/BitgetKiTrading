"use client";

import { useI18n } from "@/components/i18n/I18nProvider";
import type { LivePaperState } from "@/lib/types";

type Props = {
  paper: LivePaperState;
};

const pk = (k: string) => `live.paperPanel.${k}` as const;

export function PaperPanel({ paper }: Props) {
  const { t } = useI18n();
  return (
    <div className="panel paper-row">
      <div>
        <h2>{t(pk("title"))}</h2>
        {paper.open_positions.length === 0 ? (
          <p className="muted">{t(pk("empty"))}</p>
        ) : (
          <ul className="pos-list">
            {paper.open_positions.map((p) => (
              <li key={p.position_id}>
                <strong>{p.side}</strong> {p.qty_base} @ {p.entry_price_avg}
                <span className="pnl">
                  {" "}
                  {t(pk("upnl"))} {p.unrealized_pnl_usdt.toFixed(2)} USDT
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <h3>{t(pk("sumUpnl"))}</h3>
        <p className="pnl-big">{paper.unrealized_pnl_usdt.toFixed(2)} USDT</p>
        {paper.mark_price != null ? (
          <p className="muted">
            {t(pk("markApprox"))} {paper.mark_price}
          </p>
        ) : null}
      </div>
      <div>
        <h3>{t(pk("lastTrade"))}</h3>
        {paper.last_closed_trade ? (
          <pre className="json-mini">
            {JSON.stringify(paper.last_closed_trade, null, 0)}
          </pre>
        ) : (
          <p className="muted">{t(pk("none"))}</p>
        )}
      </div>
    </div>
  );
}
