import {
  integrationMatrixWorstRows,
  rollupIntegrationMatrix,
} from "@/lib/integration-check-summary";
import { getRequestLocale } from "@/lib/i18n/server";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import type {
  IntegrationsMatrixBlock,
  IntegrationsMatrixRow,
} from "@/lib/types";

type Props = Readonly<{
  matrix: IntegrationsMatrixBlock | null | undefined;
}>;

/**
 * Kurzes Urteil zur Integrationsmatrix: OK vs. handlungsrelevante Zeilen.
 */
function rowTitle(row: IntegrationsMatrixRow, locale: string): string {
  return locale === "en" ? row.display_name_en : row.display_name_de;
}

export async function IntegrationSummaryBanner({ matrix }: Props) {
  const t = await getServerTranslator();
  const locale = await getRequestLocale();
  const roll = rollupIntegrationMatrix(matrix);
  if (roll.total === 0) {
    return (
      <div
        className="integration-summary integration-summary--unknown"
        role="status"
      >
        <p className="integration-summary__title">
          {t("pages.integrations.summaryNoData")}
        </p>
        <p className="muted small">
          {t("pages.integrations.summaryNoDataBody")}
        </p>
      </div>
    );
  }

  const problems = matrix?.integrations
    ? integrationMatrixWorstRows(matrix.integrations)
    : [];
  const hasHard =
    roll.error > 0 ||
    roll.misconfigured > 0 ||
    roll.degraded > 0 ||
    roll.notConfigured > 0;

  const variant = hasHard
    ? "integration-summary--attention"
    : "integration-summary--ok";
  return (
    <div className={`integration-summary ${variant}`} role="status">
      <p className="integration-summary__title">
        {hasHard
          ? t("pages.integrations.summaryAttentionTitle")
          : t("pages.integrations.summaryOkTitle")}
      </p>
      <p className="muted small">
        {t("pages.integrations.summaryCounts", {
          ok: roll.ok,
          disabled: roll.disabled,
          degraded: roll.degraded + roll.notConfigured,
          bad: roll.error + roll.misconfigured,
          total: roll.total,
        })}
      </p>
      {problems.length > 0 ? (
        <ul className="integration-summary__issues small">
          {problems.map((row) => (
            <li key={row.integration_key}>
              <strong>{rowTitle(row, locale)}</strong> ({row.integration_key}):{" "}
              {row.health_status}
              {row.health_error_public ? (
                <span className="muted"> — {row.health_error_public}</span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
