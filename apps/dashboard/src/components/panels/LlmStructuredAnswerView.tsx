"use client";

import { useMemo } from "react";

import { splitExplanatoryText } from "@/lib/llm-response-layout";

export type LlmStructuredAnswerVariant =
  | "operator_explain"
  | "strategy_signal_explain";

type Translate = (
  key: string,
  vars?: Record<string, string | number | boolean>,
) => string;

export type LlmStructuredAnswerProps = Readonly<{
  variant: LlmStructuredAnswerVariant;
  isFakeProvider: boolean;
  provider?: string;
  model?: string;
  cached?: boolean;
  provenance?: Record<string, unknown> | null;
  explanation_de?: string;
  strategy_explanation_de?: string;
  referenced_artifacts_de?: string[];
  referenced_input_keys_de?: string[];
  risk_and_caveats_de?: string;
  non_authoritative_note_de?: string;
  execution_authority?: string;
  t: Translate;
}>;

function provenanceRetrievalChunks(
  prov: Record<string, unknown> | null | undefined,
): ReadonlyArray<{ id: string; shortHash?: string }> {
  if (!prov || typeof prov !== "object") return [];
  const ret = prov.retrieval;
  if (!ret || typeof ret !== "object" || Array.isArray(ret)) return [];
  const chunks = (ret as { chunks?: unknown }).chunks;
  if (!Array.isArray(chunks)) return [];
  const out: { id: string; shortHash?: string }[] = [];
  for (const c of chunks) {
    if (!c || typeof c !== "object" || Array.isArray(c)) continue;
    const id =
      typeof (c as { id?: unknown }).id === "string"
        ? (c as { id: string }).id
        : "";
    if (!id) continue;
    const h = (c as { content_sha256?: unknown }).content_sha256;
    const shortHash =
      typeof h === "string" && h.length >= 12 ? h.slice(0, 12) : undefined;
    out.push({ id, shortHash });
  }
  return out;
}

function nextStepsList(raw: string): string[] {
  return raw
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * Strukturierte Darstellung von LLM-Antworten: Kurzfassung, Details, Treiber, Risiko, Freigabe-Hinweis, naechste Schritte, Herkunft.
 */
export function LlmStructuredAnswerView({
  variant,
  isFakeProvider,
  provider,
  model,
  cached,
  provenance,
  explanation_de,
  strategy_explanation_de,
  referenced_artifacts_de,
  referenced_input_keys_de,
  risk_and_caveats_de,
  non_authoritative_note_de,
  execution_authority,
  t,
}: LlmStructuredAnswerProps) {
  const mainText =
    variant === "operator_explain" ? explanation_de : strategy_explanation_de;
  const { summary, detail } = useMemo(
    () => splitExplanatoryText(mainText),
    [mainText],
  );

  const drivers =
    variant === "operator_explain"
      ? (referenced_artifacts_de ?? []).filter((s) => s.trim().length > 0)
      : (referenced_input_keys_de ?? []).filter((s) => s.trim().length > 0);

  const nextKey =
    variant === "operator_explain"
      ? "ui.llmAnswer.nextStepsOperator"
      : "ui.llmAnswer.nextStepsStrategy";
  const nextLines = useMemo(() => nextStepsList(t(nextKey)), [t, nextKey]);

  const driverHeading =
    variant === "operator_explain"
      ? t("ui.llmAnswer.sectionDriversDocs")
      : t("ui.llmAnswer.sectionDriversFields");

  const chunks = useMemo(
    () => provenanceRetrievalChunks(provenance ?? null),
    [provenance],
  );
  const fp =
    provenance && typeof provenance.prompt_fingerprint_sha256 === "string"
      ? provenance.prompt_fingerprint_sha256.slice(0, 16)
      : null;
  const schemaId =
    provenance && typeof provenance.schema_id === "string"
      ? provenance.schema_id
      : null;
  const quantNote =
    provenance && typeof provenance.quantitative_core_note_de === "string"
      ? provenance.quantitative_core_note_de
      : null;

  const manVer =
    provenance && typeof provenance.prompt_manifest_version === "string"
      ? provenance.prompt_manifest_version.trim()
      : "";
  const taskPv =
    provenance && typeof provenance.prompt_task_version === "string"
      ? provenance.prompt_task_version.trim()
      : "";
  const govLine = [manVer && `manifest ${manVer}`, taskPv && `task ${taskPv}`]
    .filter(Boolean)
    .join(" · ");

  const hasRiskBlock =
    (risk_and_caveats_de && risk_and_caveats_de.trim().length > 0) ||
    (non_authoritative_note_de && non_authoritative_note_de.trim().length > 0);

  const authorityFooter =
    execution_authority && execution_authority !== "none"
      ? t("ui.llmAnswer.authorityUnusual")
      : t("ui.llmAnswer.authorityNone");

  return (
    <div className="llm-structured-answer">
      {isFakeProvider ? (
        <p className="msg-warn llm-structured-answer__banner" role="status">
          {t("pages.health.aiExplainFakeBanner")}
        </p>
      ) : null}

      <section
        className="llm-structured-answer__authority"
        aria-label={t("ui.llmAnswer.authorityAria")}
      >
        <h3 className="llm-structured-answer__h">
          {t("ui.llmAnswer.authorityTitle")}
        </h3>
        <p className="llm-structured-answer__p">
          {t("ui.llmAnswer.authorityBody")}
        </p>
        <p className="muted small llm-structured-answer__p">
          {authorityFooter}
        </p>
      </section>

      <section
        className="llm-structured-answer__card"
        aria-label={t("ui.llmAnswer.sectionSummaryAria")}
      >
        <h3 className="llm-structured-answer__h">
          {t("ui.llmAnswer.sectionSummary")}
        </h3>
        <div className="llm-structured-answer__body">{summary}</div>
      </section>

      {detail.length > 0 ? (
        <details className="llm-structured-answer__details">
          <summary className="llm-structured-answer__summary-btn">
            {t("ui.llmAnswer.sectionDetail")}
          </summary>
          <div className="llm-structured-answer__body llm-structured-answer__body--detail">
            {detail}
          </div>
        </details>
      ) : null}

      {drivers.length > 0 ? (
        <section
          className="llm-structured-answer__card"
          aria-label={t("ui.llmAnswer.sectionDriversAria")}
        >
          <h3 className="llm-structured-answer__h">{driverHeading}</h3>
          <ul className="llm-structured-answer__list">
            {drivers.map((line, idx) => (
              <li key={`${idx}-${line.slice(0, 40)}`}>
                {variant === "strategy_signal_explain" ? (
                  <code>{line}</code>
                ) : (
                  line
                )}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {hasRiskBlock ? (
        <section
          className="llm-structured-answer__risk"
          aria-label={t("ui.llmAnswer.sectionRiskAria")}
        >
          <h3 className="llm-structured-answer__h">
            {t("ui.llmAnswer.sectionRisk")}
          </h3>
          {risk_and_caveats_de && risk_and_caveats_de.trim().length > 0 ? (
            <div className="llm-structured-answer__body">
              {risk_and_caveats_de.trim()}
            </div>
          ) : null}
          {non_authoritative_note_de &&
          non_authoritative_note_de.trim().length > 0 ? (
            <p className="llm-structured-answer__p llm-structured-answer__p--tight">
              <strong>{t("ui.llmAnswer.riskModelNoteLead")}</strong>{" "}
              {non_authoritative_note_de.trim()}
            </p>
          ) : null}
        </section>
      ) : null}

      <section
        className="llm-structured-answer__card llm-structured-answer__card--muted"
        aria-label={t("ui.llmAnswer.sectionNextAria")}
      >
        <h3 className="llm-structured-answer__h">
          {t("ui.llmAnswer.sectionNext")}
        </h3>
        <ol className="llm-structured-answer__ol">
          {nextLines.map((line, idx) => (
            <li key={`ns-${idx}-${line.slice(0, 32)}`}>{line}</li>
          ))}
        </ol>
      </section>

      <details className="llm-structured-answer__details llm-structured-answer__details--meta">
        <summary className="llm-structured-answer__summary-btn">
          {t("ui.llmAnswer.sectionMeta")}
        </summary>
        <dl className="llm-structured-answer__dl">
          {provider ? (
            <>
              <dt>{t("ui.llmAnswer.metaProvider")}</dt>
              <dd>{provider}</dd>
            </>
          ) : null}
          {model ? (
            <>
              <dt>{t("ui.llmAnswer.metaModel")}</dt>
              <dd>{model}</dd>
            </>
          ) : null}
          {provenance?.task_type != null &&
          String(provenance.task_type).length > 0 ? (
            <>
              <dt>{t("ui.llmAnswer.metaTask")}</dt>
              <dd>{String(provenance.task_type)}</dd>
            </>
          ) : null}
          {govLine ? (
            <>
              <dt>{t("ui.llmAnswer.metaGovernance")}</dt>
              <dd className="mono-small">{govLine}</dd>
            </>
          ) : null}
          {cached === true ? (
            <>
              <dt>{t("ui.llmAnswer.metaCached")}</dt>
              <dd>{t("ui.llmAnswer.metaCachedYes")}</dd>
            </>
          ) : null}
          {schemaId ? (
            <>
              <dt>{t("ui.llmAnswer.metaSchema")}</dt>
              <dd className="mono-small">{schemaId}</dd>
            </>
          ) : null}
          {fp ? (
            <>
              <dt>{t("ui.llmAnswer.metaFingerprint")}</dt>
              <dd className="mono-small">{fp}…</dd>
            </>
          ) : null}
          {chunks.length > 0 ? (
            <>
              <dt>{t("ui.llmAnswer.metaRetrieval")}</dt>
              <dd>
                <ul className="llm-structured-answer__list llm-structured-answer__list--compact">
                  {chunks.map((c) => (
                    <li key={c.id}>
                      <span className="mono-small">{c.id}</span>
                      {c.shortHash ? (
                        <span className="muted small"> · {c.shortHash}…</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </dd>
            </>
          ) : (
            <>
              <dt>{t("ui.llmAnswer.metaRetrieval")}</dt>
              <dd className="muted small">
                {t("ui.llmAnswer.metaRetrievalNone")}
              </dd>
            </>
          )}
        </dl>
        {quantNote ? (
          <p className="muted small llm-structured-answer__quant">
            {quantNote}
          </p>
        ) : null}
      </details>
    </div>
  );
}
