import { getServerTranslator } from "@/lib/i18n/server-translate";
import type { SystemHealthServiceItem } from "@/lib/types";

type Props = Readonly<{
  services: SystemHealthServiceItem[];
}>;

function statusClass(status: string): string {
  if (status === "ok") return "integration-probe-row--ok";
  if (status === "not_configured" || status === "disabled")
    return "integration-probe-row--muted";
  if (status === "degraded") return "integration-probe-row--warn";
  return "integration-probe-row--bad";
}

/**
 * Echte Gateway-Service-Probes (HTTP /health je Dienst) — eine Zeile pro konfiguriertem Endpoint.
 */
export async function IntegrationServiceProbeTable({ services }: Props) {
  const t = await getServerTranslator();
  return (
    <div className="panel">
      <h2>{t("pages.integrations.probesTitle")}</h2>
      <p className="muted small">{t("pages.integrations.probesLead")}</p>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>{t("pages.integrations.thService")}</th>
              <th>{t("pages.integrations.thConfigured")}</th>
              <th>{t("pages.integrations.thStatus")}</th>
              <th>{t("pages.integrations.thLatency")}</th>
              <th>{t("pages.integrations.thDetail")}</th>
            </tr>
          </thead>
          <tbody>
            {services.map((s) => (
              <tr
                key={s.name}
                className={`integration-probe-row ${statusClass(s.status)}`}
              >
                <td>
                  <strong>{s.name}</strong>
                  {s.note ? <div className="muted small">{s.note}</div> : null}
                </td>
                <td>{String(s.configured)}</td>
                <td>
                  <strong>{s.status}</strong>
                  {typeof s.http_status === "number" ? (
                    <span className="muted small"> HTTP {s.http_status}</span>
                  ) : null}
                </td>
                <td>
                  {typeof s.latency_ms === "number"
                    ? `${s.latency_ms} ms`
                    : "—"}
                </td>
                <td className="small">
                  {s.detail ??
                    s.last_error ??
                    (s.failed_checks?.length
                      ? s.failed_checks.join("; ")
                      : "—")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
