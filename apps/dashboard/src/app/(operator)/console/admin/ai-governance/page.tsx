import Link from "next/link";

import { Header } from "@/components/layout/Header";
import { CONSOLE_BASE } from "@/lib/console-paths";
import { fetchAdminLlmGovernance } from "@/lib/api";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { canAccessAdminViaServer } from "@/lib/operator-session";

export const dynamic = "force-dynamic";

export default async function AdminAiGovernancePage() {
  const t = await getServerTranslator();
  const ok = await canAccessAdminViaServer();
  if (!ok) {
    return (
      <>
        <Header
          title={t("pages.adminAiGovernance.title")}
          subtitle={t("pages.adminAiGovernance.subtitle")}
        />
        <div className="panel" role="alert">
          <p className="msg-err degradation-inline" style={{ margin: 0 }}>
            {t("pages.adminAiGovernance.deniedBody")}
          </p>
        </div>
      </>
    );
  }

  let error: string | null = null;
  let data: Awaited<ReturnType<typeof fetchAdminLlmGovernance>> | null = null;
  try {
    data = await fetchAdminLlmGovernance();
  } catch (e) {
    error = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  return (
    <>
      <Header
        title={t("pages.adminAiGovernance.title")}
        subtitle={t("pages.adminAiGovernance.subtitle")}
      />
      <p className="muted small" style={{ marginBottom: "1rem" }}>
        <Link href={`${CONSOLE_BASE}/admin`}>
          {t("pages.adminAiGovernance.backToAdmin")}
        </Link>
      </p>
      {error ? (
        <div className="panel" role="alert">
          <p className="msg-err" style={{ margin: 0 }}>
            {t("pages.adminAiGovernance.loadError")} {error}
          </p>
        </div>
      ) : data ? (
        <>
          <div className="panel" style={{ marginBottom: "1rem" }}>
            <h2 className="small" style={{ marginTop: 0 }}>
              {t("pages.adminAiGovernance.manifestLabel")}
            </h2>
            <dl className="muted small" style={{ margin: 0 }}>
              <dt>{t("pages.adminAiGovernance.manifestVersionLabel")}</dt>
              <dd>{data.summary.prompt_manifest_version}</dd>
              <dt>{t("pages.adminAiGovernance.guardrailsLabel")}</dt>
              <dd>{data.summary.guardrails_version}</dd>
              <dt>{t("pages.adminAiGovernance.evalBaselineLabel")}</dt>
              <dd>{data.summary.eval_baseline_sha256_prefix || "—"}</dd>
            </dl>
            {data.summary.eval_hint_de ? (
              <p className="muted small" style={{ marginBottom: 0 }}>
                {data.summary.eval_hint_de}
              </p>
            ) : null}
          </div>
          {data.summary.system_prompt?.global_version ? (
            <div className="panel" style={{ marginBottom: "1rem" }}>
              <h2 className="small" style={{ marginTop: 0 }}>
                {t("pages.adminAiGovernance.systemPromptTitle")}
              </h2>
              <dl className="muted small" style={{ margin: 0 }}>
                <dt>{t("pages.adminAiGovernance.systemPromptVersion")}</dt>
                <dd>{data.summary.system_prompt.global_version}</dd>
                <dt>{t("pages.adminAiGovernance.systemPromptChars")}</dt>
                <dd>{data.summary.system_prompt.global_instruction_chars}</dd>
              </dl>
            </div>
          ) : null}
          {data.summary.eval_regression?.cases?.length ? (
            <div className="panel" style={{ marginBottom: "1rem" }}>
              <h2 className="small" style={{ marginTop: 0 }}>
                {t("pages.adminAiGovernance.evalRegressionTitle")}
              </h2>
              <dl className="muted small" style={{ margin: "0 0 0.75rem 0" }}>
                <dt>{t("pages.adminAiGovernance.evalBaselineId")}</dt>
                <dd>{data.summary.eval_regression.baseline_id || "—"}</dd>
                <dt>{t("pages.adminAiGovernance.evalReleaseGate")}</dt>
                <dd>
                  {data.summary.eval_regression.release_gate
                    ? t("account.yes")
                    : t("account.no")}
                </dd>
                <dt>{t("pages.adminAiGovernance.evalCaseCount")}</dt>
                <dd>{data.summary.eval_regression.case_count}</dd>
              </dl>
              <div style={{ overflowX: "auto" }}>
                <table
                  className="muted small"
                  style={{ width: "100%", borderCollapse: "collapse" }}
                >
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left", padding: "6px 8px" }}>
                        {t("pages.adminAiGovernance.evalCaseId")}
                      </th>
                      <th style={{ textAlign: "left", padding: "6px 8px" }}>
                        {t("pages.adminAiGovernance.evalCaseCategory")}
                      </th>
                      <th style={{ textAlign: "left", padding: "6px 8px" }}>
                        {t("pages.adminAiGovernance.evalCaseDescription")}
                      </th>
                      <th style={{ textAlign: "left", padding: "6px 8px" }}>
                        {t("pages.adminAiGovernance.evalCaseTasks")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.summary.eval_regression.cases.map((row) => (
                      <tr key={row.id}>
                        <td
                          style={{ padding: "6px 8px", verticalAlign: "top" }}
                        >
                          {row.id}
                        </td>
                        <td
                          style={{ padding: "6px 8px", verticalAlign: "top" }}
                        >
                          {row.category}
                        </td>
                        <td
                          style={{ padding: "6px 8px", verticalAlign: "top" }}
                        >
                          {row.description_de}
                        </td>
                        <td
                          style={{ padding: "6px 8px", verticalAlign: "top" }}
                        >
                          {(row.task_types || []).join(", ") || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
          <div className="panel" style={{ marginBottom: "1rem" }}>
            <h2 className="small" style={{ marginTop: 0 }}>
              {t("pages.adminAiGovernance.modelLabel")}
            </h2>
            <ul
              className="muted small"
              style={{ margin: 0, paddingLeft: "1.2rem" }}
            >
              <li>
                {t("pages.adminAiGovernance.modelPrimary")}:{" "}
                {data.summary.model_mapping.openai_model_primary}
              </li>
              <li>
                {t("pages.adminAiGovernance.fakeProvider")}:{" "}
                {data.summary.model_mapping.llm_use_fake_provider
                  ? t("account.yes")
                  : t("account.no")}
              </li>
            </ul>
            <h3 className="small">
              {t("pages.adminAiGovernance.orchestratorHealth")}
            </h3>
            <pre
              className="muted small"
              style={{ overflow: "auto", maxWidth: "100%" }}
            >
              {JSON.stringify(data.summary.orchestrator_health, null, 2)}
            </pre>
          </div>
          <div className="panel" style={{ marginBottom: "1rem" }}>
            <h2 className="small" style={{ marginTop: 0 }}>
              {t("pages.adminAiGovernance.tasksTitle")}
            </h2>
            <div style={{ overflowX: "auto" }}>
              <table
                className="muted small"
                style={{ width: "100%", borderCollapse: "collapse" }}
              >
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", padding: "6px 8px" }}>
                      {t("pages.adminAiGovernance.taskId")}
                    </th>
                    <th style={{ textAlign: "left", padding: "6px 8px" }}>
                      {t("pages.adminAiGovernance.promptVersion")}
                    </th>
                    <th style={{ textAlign: "left", padding: "6px 8px" }}>
                      {t("pages.adminAiGovernance.status")}
                    </th>
                    <th style={{ textAlign: "left", padding: "6px 8px" }}>
                      {t("pages.adminAiGovernance.guardrailTier")}
                    </th>
                    <th style={{ textAlign: "left", padding: "6px 8px" }}>
                      {t("pages.adminAiGovernance.schemaFile")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.summary.tasks.map((row) => (
                    <tr key={row.task_id}>
                      <td style={{ padding: "6px 8px", verticalAlign: "top" }}>
                        {row.task_id}
                      </td>
                      <td style={{ padding: "6px 8px", verticalAlign: "top" }}>
                        {row.prompt_version}
                      </td>
                      <td style={{ padding: "6px 8px", verticalAlign: "top" }}>
                        {row.status}
                      </td>
                      <td style={{ padding: "6px 8px", verticalAlign: "top" }}>
                        {row.guardrail_tier}
                      </td>
                      <td style={{ padding: "6px 8px", verticalAlign: "top" }}>
                        {row.schema_filename ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="panel">
            <h2 className="small" style={{ marginTop: 0 }}>
              {t("pages.adminAiGovernance.evalScoresTitle")}
            </h2>
            <p className="muted small" style={{ marginTop: 0 }}>
              {data.eval_scores_placeholder.hint_de}
            </p>
          </div>
        </>
      ) : null}
    </>
  );
}
