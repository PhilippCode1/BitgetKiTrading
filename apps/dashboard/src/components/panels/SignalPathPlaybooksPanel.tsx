import Link from "next/link";

import { consolePath } from "@/lib/console-paths";
import { formatTsMs } from "@/lib/format";
import type { SignalPathPlaybookUnlinkedItem } from "@/lib/types";

type Translate = (key: string) => string;

export function SignalPathPlaybooksPanel({
  items,
  t,
}: Readonly<{
  items: SignalPathPlaybookUnlinkedItem[];
  t: Translate;
}>) {
  if (items.length === 0) {
    return null;
  }
  return (
    <div
      className="panel"
      role="region"
      aria-label={t("pages.strategiesList.signalPathPanelAria")}
    >
      <h2>{t("pages.strategiesList.signalPathPanelTitle")}</h2>
      <p className="muted small">
        {t("pages.strategiesList.signalPathPanelLead")}
      </p>
      <div className="table-wrap" style={{ marginTop: 12 }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>{t("pages.strategiesList.signalPathThKey")}</th>
              <th>{t("pages.strategiesList.signalPathThFamily")}</th>
              <th>{t("pages.strategiesList.signalPathThCount")}</th>
              <th>{t("pages.strategiesList.signalPathThLast")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.playbook_key}>
                <td className="mono-small">{p.playbook_key}</td>
                <td>{p.playbook_family ?? "—"}</td>
                <td>{p.signal_count}</td>
                <td>{formatTsMs(p.last_signal_ts_ms)}</td>
                <td>
                  <Link
                    href={`${consolePath("signals")}?signal_registry_key=${encodeURIComponent(p.playbook_key)}`}
                  >
                    {t("pages.strategiesList.signalPathOpenSignals")}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
