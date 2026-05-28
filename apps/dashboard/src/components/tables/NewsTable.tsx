import Link from "next/link";

import { consolePath } from "@/lib/console-paths";
import { formatTsMs } from "@/lib/format";
import type { NewsScoredItem } from "@/lib/types";

type Props = Readonly<{
  items: NewsScoredItem[];
  emptyMessage: string;
  detailLinkLabel: string;
  thScore: string;
  thSentiment: string;
  thImpact: string;
  thTitle: string;
  thSource: string;
  thTime: string;
}>;

export function NewsTable({
  items,
  emptyMessage,
  detailLinkLabel,
  thScore,
  thSentiment,
  thImpact,
  thTitle,
  thSource,
  thTime,
}: Props) {
  if (items.length === 0) {
    return <p className="muted">{emptyMessage}</p>;
  }
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>{thScore}</th>
            <th>{thSentiment}</th>
            <th>{thImpact}</th>
            <th>{thTitle}</th>
            <th>{thSource}</th>
            <th>{thTime}</th>
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
