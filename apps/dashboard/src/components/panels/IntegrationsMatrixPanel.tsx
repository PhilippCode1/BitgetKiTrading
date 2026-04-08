"use client";

import Link from "next/link";

import { useI18n } from "@/components/i18n/I18nProvider";
import { consolePath } from "@/lib/console-paths";
import type {
  IntegrationsMatrixBlock,
  IntegrationsMatrixRow,
} from "@/lib/types";

type Props = Readonly<{
  matrix: IntegrationsMatrixBlock | null | undefined;
}>;

function formatFlags(flags: Record<string, unknown>): string {
  return Object.entries(flags)
    .map(([k, v]) => `${k}=${String(v)}`)
    .join(", ");
}

function statusPillClass(status: string): string {
  if (status === "ok")
    return "integration-status-pill integration-status-pill--ok";
  if (status === "disabled")
    return "integration-status-pill integration-status-pill--disabled";
  if (status === "degraded" || status === "not_configured") {
    return "integration-status-pill integration-status-pill--warn";
  }
  return "integration-status-pill integration-status-pill--bad";
}

export function IntegrationsMatrixPanel({ matrix }: Props) {
  const { t, locale } = useI18n();

  if (!matrix?.integrations?.length) {
    return (
      <div className="panel">
        <h2>{t("pages.health.matrixTitle")}</h2>
        <p className="muted">{t("pages.health.matrixUnavailable")}</p>
      </div>
    );
  }

  const policyNote =
    locale === "en"
      ? matrix.credential_policy.note_en
      : matrix.credential_policy.note_de;

  const displayName = (row: IntegrationsMatrixRow) =>
    locale === "en" ? row.display_name_en : row.display_name_de;

  return (
    <div className="panel">
      <h2>{t("pages.health.matrixTitle")}</h2>
      <p className="muted small">{t("pages.health.matrixLead")}</p>
      <p className="muted small">
        <Link href={consolePath("integrations")}>
          {t("console.nav.integrations")}
        </Link>
      </p>
      <p className="muted small">
        {t("pages.health.matrixVault")}:{" "}
        <code>{matrix.credential_policy.vault_mode}</code>
        {" — "}
        {policyNote}
      </p>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>{t("pages.health.matrixThIntegration")}</th>
              <th>{t("pages.health.matrixThStatus")}</th>
              <th>{t("pages.health.matrixThFlags")}</th>
              <th>{t("pages.health.matrixThErrorNow")}</th>
              <th>{t("pages.health.matrixThErrorPersisted")}</th>
              <th>{t("pages.health.matrixThLastOk")}</th>
              <th>{t("pages.health.matrixThLastFail")}</th>
              <th>{t("pages.health.matrixThRefs")}</th>
            </tr>
          </thead>
          <tbody>
            {matrix.integrations.map((row) => (
              <tr key={row.integration_key}>
                <td>
                  <strong>{displayName(row)}</strong>
                  <div className="muted small">{row.integration_key}</div>
                </td>
                <td>
                  <span className={statusPillClass(row.health_status)}>
                    {(() => {
                      const sk = `pages.integrations.matrixStatus.${row.health_status}`;
                      const lbl = t(sk);
                      return lbl !== sk ? lbl : row.health_status;
                    })()}
                  </span>
                </td>
                <td className="small muted" style={{ maxWidth: "14rem" }}>
                  {formatFlags(row.feature_flags)}
                </td>
                <td className="small">{row.health_error_public ?? "—"}</td>
                <td className="small">{row.last_error_persisted ?? "—"}</td>
                <td className="small">{row.last_success_ts ?? "—"}</td>
                <td className="small">{row.last_failure_ts ?? "—"}</td>
                <td className="small muted">
                  {(row.credential_refs ?? []).join(", ") || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        {t("pages.health.matrixProbeNote")}: {String(matrix.server_ts_ms)}
      </p>
    </div>
  );
}
