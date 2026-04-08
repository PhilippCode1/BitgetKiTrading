"use client";

import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import { LlmStructuredAnswerView } from "@/components/panels/LlmStructuredAnswerView";
import {
  OPERATOR_EXPLAIN_CONTEXT_JSON_MAX_BYTES,
  readonlyContextJsonUtf8ByteLength,
} from "@/lib/operator-explain-context";
import {
  isOperatorExplainSuccessPayload,
  resolveNetworkFailure,
  resolveOperatorExplainFailure,
  sanitizePublicErrorMessage,
} from "@/lib/operator-explain-errors";
import { severityRank } from "@/lib/product-messages/schema";
import type { ProductMessage } from "@/lib/product-messages/schema";
import {
  buildProductMessageSituationExplainContext,
  buildSituationOperatorExplainContext,
  buildSurfaceSituationExplainContext,
} from "@/lib/situation-explain/build-llm-context";
import {
  buildDeterministicSituationExplainFromProductMessage,
  buildDeterministicSituationExplainFromSnapshot,
  buildDeterministicSituationExplainFromSurfaceBrief,
} from "@/lib/situation-explain/build-deterministic";
import type { SituationExplainSections } from "@/lib/situation-explain/types";
import type { SelfHealingSnapshot } from "@/lib/self-healing/schema";
import type { SurfaceDiagnosticModel } from "@/lib/surface-diagnostic-catalog";

const CLIENT_FETCH_TIMEOUT_MS = 128_000;

type Envelope = Readonly<{
  ok?: boolean;
  provider?: string;
  model?: string;
  cached?: boolean;
  result?: {
    schema_version?: string;
    execution_authority?: string;
    explanation_de?: string;
    referenced_artifacts_de?: string[];
    non_authoritative_note_de?: string;
  };
  provenance?: Record<string, unknown>;
}>;

export type SituationAiExplainPanelProps = Readonly<
  | { variant: "snapshot"; snapshot: SelfHealingSnapshot }
  | { variant: "product_message"; message: ProductMessage }
  | {
      variant: "surface";
      model: SurfaceDiagnosticModel;
      title: string;
      lead: string;
    }
>;

function sectionBlock(
  label: string,
  body: string,
  key: string,
): ReactNode {
  const b = body.trim();
  if (!b) return null;
  return (
    <div className="situation-ai-explain__block" key={key}>
      <h4 className="situation-ai-explain__label">{label}</h4>
      <div
        className="situation-ai-explain__body"
        style={{ whiteSpace: "pre-wrap" }}
      >
        {b}
      </div>
    </div>
  );
}

function productMessageAllowsDeepExplain(m: ProductMessage): boolean {
  return severityRank(m.severity) >= severityRank("hint");
}

export function SituationAiExplainPanel(props: SituationAiExplainPanelProps) {
  const { t, locale } = useI18n();
  const [loading, setLoading] = useState(false);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [envelope, setEnvelope] = useState<Envelope | null>(null);
  const [traceMeta, setTraceMeta] = useState<{
    rid?: string;
    cid?: string;
  } | null>(null);
  const [llmOpen, setLlmOpen] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const userCancelledRef = useRef(false);
  const teardownRef = useRef(false);
  const mountedRef = useRef(true);
  const submitLockRef = useRef(false);

  const deterministic: SituationExplainSections = useMemo(() => {
    if (props.variant === "snapshot") {
      return buildDeterministicSituationExplainFromSnapshot(
        props.snapshot,
        t,
      );
    }
    if (props.variant === "product_message") {
      return buildDeterministicSituationExplainFromProductMessage(
        props.message,
        t,
      );
    }
    return buildDeterministicSituationExplainFromSurfaceBrief(
      {
        title: props.title,
        lead: props.lead,
        surfaceId: props.model.id,
        contextOverlay: props.model.contextOverlay,
      },
      t,
    );
  }, [props, t]);

  const readonlyContextJson = useMemo((): Record<string, unknown> => {
    if (props.variant === "snapshot") {
      return buildSituationOperatorExplainContext(
        props.snapshot,
        deterministic,
      );
    }
    if (props.variant === "product_message") {
      return buildProductMessageSituationExplainContext(
        props.message,
        deterministic,
      );
    }
    return buildSurfaceSituationExplainContext({
      surfaceId: props.model.id,
      messageBaseKey: props.model.messageBaseKey,
      contextOverlay: props.model.contextOverlay,
      deterministic,
    });
  }, [props, deterministic]);

  const canRunLlm = useMemo(() => {
    if (props.variant === "product_message") {
      return productMessageAllowsDeepExplain(props.message);
    }
    return true;
  }, [props]);

  useEffect(() => {
    if (!loading) {
      setElapsedSec(0);
      return;
    }
    setElapsedSec(0);
    const id = window.setInterval(() => {
      setElapsedSec((s) => s + 1);
    }, 1000);
    return () => window.clearInterval(id);
  }, [loading]);

  useEffect(() => {
    mountedRef.current = true;
    teardownRef.current = false;
    return () => {
      teardownRef.current = true;
      mountedRef.current = false;
      abortRef.current?.abort();
    };
  }, []);

  const cancelInFlight = useCallback(() => {
    userCancelledRef.current = true;
    abortRef.current?.abort();
  }, []);

  const runLlm = useCallback(async () => {
    setError(null);
    const ctxBytes = readonlyContextJsonUtf8ByteLength(readonlyContextJson);
    if (ctxBytes > OPERATOR_EXPLAIN_CONTEXT_JSON_MAX_BYTES) {
      setError(t("pages.health.aiExplainErrContextTooLarge"));
      return;
    }
    if (submitLockRef.current) return;
    submitLockRef.current = true;
    userCancelledRef.current = false;
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    const timeoutId = window.setTimeout(
      () => ac.abort(),
      CLIENT_FETCH_TIMEOUT_MS,
    );

    setEnvelope(null);
    setTraceMeta(null);
    setLoading(true);

    const question_de =
      locale === "en"
        ? t("situationAiExplain.llmQuestionEn")
        : t("situationAiExplain.llmQuestion");

    try {
      const res = await fetch("/api/dashboard/llm/operator-explain", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question_de, readonly_context_json: readonlyContextJson }),
        cache: "no-store",
        signal: ac.signal,
      });
      const text = await res.text();
      if (!mountedRef.current) return;
      const hdrRid = res.headers.get("x-request-id")?.trim();
      const hdrCid = res.headers.get("x-correlation-id")?.trim();
      if (hdrRid || hdrCid) {
        setTraceMeta({ rid: hdrRid, cid: hdrCid });
      }
      if (!res.ok) {
        setError(resolveOperatorExplainFailure(res.status, text, t));
        return;
      }
      let parsed: unknown;
      try {
        parsed = JSON.parse(text) as unknown;
      } catch {
        setError(t("pages.health.aiExplainErrBadJson"));
        return;
      }
      if (!isOperatorExplainSuccessPayload(parsed)) {
        if (
          parsed !== null &&
          typeof parsed === "object" &&
          !Array.isArray(parsed) &&
          (parsed as Envelope).ok === false
        ) {
          setError(t("pages.health.aiExplainErrUpstreamNotOk"));
          return;
        }
        setError(t("pages.health.aiExplainErrIncompleteResponse"));
        return;
      }
      setEnvelope(parsed as Envelope);
    } catch (e) {
      if (!mountedRef.current) return;
      if (e instanceof DOMException && e.name === "AbortError") {
        if (teardownRef.current) return;
        if (userCancelledRef.current) {
          setError(t("pages.health.aiExplainErrAborted"));
        } else {
          setError(t("pages.health.aiExplainErrTimeout"));
        }
        return;
      }
      const net = resolveNetworkFailure(e, t);
      if (net) {
        setError(net);
        return;
      }
      const msg = e instanceof Error ? e.message : String(e);
      setError(
        `${t("pages.health.aiExplainErrNetwork")} ${sanitizePublicErrorMessage(msg) || t("pages.health.aiExplainErrUnknown")}`,
      );
    } finally {
      window.clearTimeout(timeoutId);
      submitLockRef.current = false;
      abortRef.current = null;
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [locale, readonlyContextJson, t]);

  const result = envelope?.result;
  const showLlmResult = Boolean(
    result &&
      envelope &&
      envelope.ok !== false &&
      isOperatorExplainSuccessPayload(envelope),
  );

  const isFake =
    (envelope?.provider ?? "").toLowerCase() === "fake" ||
    (envelope?.model ?? "").toLowerCase().includes("fake");

  return (
    <section
      className="situation-ai-explain"
      aria-label={t("situationAiExplain.panelAria")}
    >
      <h3 className="situation-ai-explain__title">
        {t("situationAiExplain.title")}
      </h3>
      <p className="muted small situation-ai-explain__lead">
        {t("situationAiExplain.lead")}
      </p>
      {deterministic.hasUncertainty ? (
        <p className="msg-warn situation-ai-explain__uncertain" role="status">
          {t("situationAiExplain.uncertaintyBanner")}
        </p>
      ) : null}

      <div className="situation-ai-explain__sections">
        {sectionBlock(
          t("situationAiExplain.section.problem"),
          deterministic.problemPlain,
          "p",
        )}
        {sectionBlock(
          t("situationAiExplain.section.technical"),
          deterministic.technicalCause,
          "t",
        )}
        {sectionBlock(
          t("situationAiExplain.section.why"),
          deterministic.whyItMatters,
          "w",
        )}
        {sectionBlock(
          t("situationAiExplain.section.areas"),
          deterministic.affectedAreas,
          "a",
        )}
        {sectionBlock(
          t("situationAiExplain.section.appTried"),
          deterministic.appAlreadyTried,
          "ap",
        )}
        {sectionBlock(
          t("situationAiExplain.section.next"),
          deterministic.nextRecommended,
          "n",
        )}
        {sectionBlock(
          t("situationAiExplain.section.selfHeal"),
          deterministic.selfHealVsManual,
          "s",
        )}
      </div>

      {canRunLlm ? (
        <details
          className="situation-ai-explain__llm"
          open={llmOpen}
          onToggle={(e) => setLlmOpen((e.target as HTMLDetailsElement).open)}
        >
          <summary className="situation-ai-explain__llm-sum">
            {t("situationAiExplain.llmFoldTitle")}
          </summary>
          <p className="muted small">{t("situationAiExplain.llmFoldLead")}</p>
          <div className="situation-ai-explain__llm-actions">
            <button
              type="button"
              className="public-btn primary"
              disabled={loading}
              onClick={() => void runLlm()}
            >
              {loading
                ? `${t("pages.health.aiExplainLoadingShort")} (${elapsedSec}s)`
                : t("situationAiExplain.btnRunLlm")}
            </button>
            {loading ? (
              <button
                type="button"
                className="public-btn ghost"
                onClick={cancelInFlight}
              >
                {t("pages.health.aiExplainCancel")}
              </button>
            ) : null}
          </div>
          {error ? (
            <p className="msg-err situation-ai-explain__llm-err" role="alert">
              {t("pages.health.aiExplainErrPrefix")} {error}
            </p>
          ) : null}
          {showLlmResult && result ? (
            <div className="situation-ai-explain__llm-out">
              <LlmStructuredAnswerView
                variant="operator_explain"
                isFakeProvider={isFake}
                provider={envelope?.provider}
                model={envelope?.model}
                cached={envelope?.cached}
                provenance={envelope?.provenance ?? null}
                explanation_de={result.explanation_de}
                referenced_artifacts_de={result.referenced_artifacts_de}
                non_authoritative_note_de={result.non_authoritative_note_de}
                execution_authority={result.execution_authority}
                t={t}
              />
              {traceMeta?.rid || traceMeta?.cid ? (
                <p className="muted small" style={{ marginTop: 8 }}>
                  {traceMeta.rid
                    ? `${t("pages.health.aiExplainTraceRequestId")}: ${traceMeta.rid}`
                    : null}
                  {traceMeta.rid && traceMeta.cid ? " · " : null}
                  {traceMeta.cid
                    ? `${t("pages.health.aiExplainTraceCorrelationId")}: ${traceMeta.cid}`
                    : null}
                </p>
              ) : null}
            </div>
          ) : null}
        </details>
      ) : (
        <p className="muted small">{t("situationAiExplain.llmSkippedLowSeverity")}</p>
      )}
    </section>
  );
}
