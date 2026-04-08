"use client";

import type { ReactNode } from "react";

type Translate = (
  key: string,
  vars?: Record<string, string | number | boolean>,
) => string;

export type SafetyDiagnosisResult = Readonly<{
  incident_summary_de?: string;
  root_causes_de?: string[];
  affected_services_de?: string[];
  affected_repo_paths_de?: string[];
  recommended_next_steps_de?: string[];
  proposed_commands_de?: string[];
  env_or_config_hints_de?: string[];
  non_authoritative_note_de?: string;
  separation_note_de?: string;
  execution_authority?: string;
}>;

function ListBlock({
  title,
  items,
  className,
}: Readonly<{
  title: string;
  items: readonly string[];
  className?: string;
}>) {
  if (!items.length) return null;
  return (
    <div className={className}>
      <h3 className="h3-quiet">{title}</h3>
      <ul className="news-list">
        {items.map((line, i) => (
          <li key={`${i}-${line.slice(0, 48)}`}>{line}</li>
        ))}
      </ul>
    </div>
  );
}

function CommandBlock({
  title,
  items,
  warnLabel,
}: Readonly<{ title: string; items: readonly string[]; warnLabel: string }>) {
  if (!items.length) return null;
  return (
    <div className="safety-diag-commands">
      <p className="warn-banner" role="status">
        <strong>{warnLabel}</strong>
      </p>
      <h3 className="h3-quiet">{title}</h3>
      <ul className="news-list safety-diag-commands__list">
        {items.map((line, i) => (
          <li key={`c-${i}`}>
            <code className="safety-diag-commands__code">{line}</code>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SafetyDiagnosisResultView({
  result,
  isFakeProvider,
  provider,
  model,
  provenance,
  t,
}: Readonly<{
  result: SafetyDiagnosisResult;
  isFakeProvider: boolean;
  provider?: string;
  model?: string;
  provenance?: Record<string, unknown> | null;
  t: Translate;
}>) {
  const metaLine: ReactNode[] = [];
  if (provider) {
    metaLine.push(
      <span key="p">
        {t("pages.health.safetyDiagProvider")}: {provider}
      </span>,
    );
  }
  if (model) {
    metaLine.push(
      <span key="m">
        {" "}
        · {t("pages.health.safetyDiagModel")}: {model}
      </span>,
    );
  }

  return (
    <div className="safety-diag-result" role="region">
      {isFakeProvider ? (
        <p className="warn-banner" role="status">
          {t("pages.health.safetyDiagFakeBanner")}
        </p>
      ) : null}
      {metaLine.length > 0 ? <p className="muted small">{metaLine}</p> : null}
      <div className="safety-diag-result__summary">
        <h3 className="h3-quiet">
          {t("pages.health.safetyDiagSummaryHeading")}
        </h3>
        <p className="safety-diag-result__summary-text">
          {result.incident_summary_de ?? "—"}
        </p>
      </div>
      <ListBlock
        title={t("pages.health.safetyDiagRootCauses")}
        items={result.root_causes_de ?? []}
      />
      <ListBlock
        title={t("pages.health.safetyDiagServices")}
        items={result.affected_services_de ?? []}
      />
      <ListBlock
        title={t("pages.health.safetyDiagRepoPaths")}
        items={result.affected_repo_paths_de ?? []}
      />
      <ListBlock
        title={t("pages.health.safetyDiagNextSteps")}
        items={result.recommended_next_steps_de ?? []}
      />
      <ListBlock
        title={t("pages.health.safetyDiagEnvHints")}
        items={result.env_or_config_hints_de ?? []}
      />
      <CommandBlock
        title={t("pages.health.safetyDiagProposedCommands")}
        items={result.proposed_commands_de ?? []}
        warnLabel={t("pages.health.safetyDiagCommandsWarn")}
      />
      {result.separation_note_de ? (
        <p className="muted small safety-diag-result__sep">
          <strong>{t("pages.health.safetyDiagSeparation")}</strong>{" "}
          {result.separation_note_de}
        </p>
      ) : null}
      {result.non_authoritative_note_de ? (
        <p className="muted small">
          <strong>{t("pages.health.safetyDiagNonAuth")}</strong>{" "}
          {result.non_authoritative_note_de}
        </p>
      ) : null}
      {provenance &&
      typeof provenance.task_type === "string" &&
      provenance.task_type ? (
        <p className="muted small" role="status">
          {t("pages.health.safetyDiagTaskType")}: {provenance.task_type}
          {result.execution_authority ? (
            <>
              {" "}
              · {t("pages.health.safetyDiagExecAuth")}:{" "}
              {result.execution_authority}
            </>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}
