import Link from "next/link";

import { consolePath } from "@/lib/console-paths";
import { formatTsMs } from "@/lib/format";
import type { NewsScoredItem } from "@/lib/types";

type Props = Readonly<{
  items: NewsScoredItem[];
  emptyMessage: string;
  detailLinkLabel: string;
}>;

export function NewsTable({ items, emptyMessage, detailLinkLabel }: Props) {
  if (items.length === 0) {
    return <p className="muted">{emptyMessage}</p>;
  }
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Score</th>
            <th>Sentiment</th>
            <th>Impact</th>
            <th>Titel</th>
            <th>Quelle</th>
            <th>Zeit</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((n) => (
            <tr key={n.news_id}>
              <td>{n.score_0_100}</td>
              <td>{n.sentiment ?? "—"}</td>
              <td>{n.impact_window ?? "—"}</td>
              <td>{n.title ?? "—"}</td>
              <td>{n.source ?? "—"}</td>
              <td>{formatTsMs(n.published_ts_ms)}</td>
              <td>
                <Link href={consolePath(`news/${n.news_id}`)}>
                  {detailLinkLabel}
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
