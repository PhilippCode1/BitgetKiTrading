"use client";

import { memo, useCallback, useEffect, useRef, useState } from "react";

import { SurfaceDiagnosticCard } from "@/components/diagnostics/SurfaceDiagnosticCard";
import { useI18n } from "@/components/i18n/I18nProvider";
import { LlmStructuredAnswerView } from "@/components/panels/LlmStructuredAnswerView";
import {
  OPERATOR_EXPLAIN_CONTEXT_JSON_MAX_BYTES,
  OPERATOR_EXPLAIN_CONTEXT_TEXTAREA_MAX_CHARS,
  readonlyContextJsonUtf8ByteLength,
} from "@/lib/operator-explain-context";
import {
  isOperatorExplainSuccessPayload,
  resolveNetworkFailure,
  resolveOperatorExplainFailure,
  sanitizePublicErrorMessage,
} from "@/lib/operator-explain-errors";
import { resolveOperatorExplainLlmSurfaceDiagnostic } from "@/lib/surface-diagnostic-catalog";

const QUESTION_MAX = 8000;
/** Etwas ueber BFF-Upstream-Timeout (125s), damit zuerst das Gateway antwortet. */
const CLIENT_FETCH_TIMEOUT_MS = 128_000;

type OperatorExplainResult = {
  schema_version?: string;
  execution_authority?: string;
  explanation_de?: string;
  referenced_artifacts_de?: string[];
  non_authoritative_note_de?: string;
};

type Envelope = {
  ok?: boolean;
  provider?: string;
  model?: string;
  cached?: boolean;
  result?: OperatorExplainResult;
  provenance?: Record<string, unknown>;
};

function OperatorExplainPanelInner() {
  const { t } = useI18n();
  const [question, setQuestion] = useState("");
  const [contextText, setContextText] = useState("");
  const [loading, setLoading] = useState(false);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [envelope, setEnvelope] = useState<Envelope | null>(null);
  const [traceMeta, setTraceMeta] = useState<{
    rid?: string;
    cid?: string;
  } | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const userCancelledRef = useRef(false);
  const teardownRef = useRef(false);
  const mountedRef = useRef(true);
  const submitLockRef = useRef(false);

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

  const submit = useCallback(async () => {
    setError(null);
    const q = question.trim();
    if (q.length < 3) {
      setError(t("pages.health.aiExplainErrQuestionShort"));
      return;
    }
    if (q.length > QUESTION_MAX) {
      setError(t("pages.health.aiExplainErrQuestionLong"));
      return;
    }
    let readonly_context_json: Record<string, unknown> = {};
    const raw = contextText.trim();
    if (raw.length > OPERATOR_EXPLAIN_CONTEXT_TEXTAREA_MAX_CHARS) {
      setError(t("pages.health.aiExplainErrContextTooLarge"));
      return;
    }
    if (raw.length > 0) {
      try {
        const parsed = JSON.parse(raw) as unknown;
        if (
          parsed === null ||
          typeof parsed !== "object" ||
          Array.isArray(parsed)
        ) {
          setError(t("pages.health.aiExplainErrContextNotObject"));
          return;
        }
        readonly_context_json = parsed as Record<string, unknown>;
        if (
          readonlyContextJsonUtf8ByteLength(readonly_context_json) >
          OPERATOR_EXPLAIN_CONTEXT_JSON_MAX_BYTES
        ) {
          setError(t("pages.health.aiExplainErrContextTooLarge"));
          return;
        }
      } catch {
        setError(t("pages.health.aiExplainErrContextJson"));
        return;
      }
    }

    if (submitLockRef.current) {
      return;
    }
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

    try {
      const res = await fetch("/api/dashboard/llm/operator-explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question_de: q, readonly_context_json }),
        cache: "no-store",
        signal: ac.signal,
      });
      const text = await res.text();
      if (!mountedRef.current) {
        return;
      }
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
      if (!mountedRef.current) {
        return;
      }
      if (e instanceof DOMException && e.name === "AbortError") {
        if (teardownRef.current) {
          return;
        }
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
  }, [contextText, question, t]);

  const result = envelope?.result;
  const showResult = Boolean(
    result &&
    envelope &&
    envelope.ok !== false &&
    isOperatorExplainSuccessPayload(envelope),
  );
  return (
    <div className="panel operator-explain-panel">
      <h2>{t("pages.health.aiExplainTitle")}</h2>
      <p className="muted small">{t("pages.health.aiExplainLead")}</p>
      <section
        aria-busy={loading}
        aria-label={t("pages.health.aiExplainFormHeading")}
        style={{ marginTop: "0.75rem" }}
      >
        <div className="operator-explain-panel__fields">
          <label className="small operator-explain-panel__label">
            <span className="muted">
              {t("pages.health.aiExplainQuestionLabel")}
            </span>
            <textarea
              className="operator-explain-panel__textarea"
              rows={3}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={t("pages.health.aiExplainQuestionPlaceholder")}
              disabled={loading}
              autoComplete="off"
              maxLength={QUESTION_MAX}
            />
            <span className="muted small operator-explain-panel__counter">
              {question.length}/{QUESTION_MAX}
            </span>
          </label>
          <label className="small operator-explain-panel__label">
            <span className="muted">
              {t("pages.health.aiExplainContextLabel")}
            </span>
            <span className="muted small operator-explain-panel__hint">
              {t("pages.health.aiExplainContextHint")}
            </span>
            <textarea
              className="operator-explain-panel__textarea operator-explain-panel__textarea--mono"
              rows={5}
              value={contextText}
              onChange={(e) => setContextText(e.target.value)}
              placeholder={t("pages.health.aiExplainContextPlaceholder")}
              disabled={loading}
              spellCheck={false}
              autoComplete="off"
              maxLength={OPERATOR_EXPLAIN_CONTEXT_TEXTAREA_MAX_CHARS}
            />
            <span className="muted small operator-explain-panel__counter">
              {contextText.length}/{OPERATOR_EXPLAIN_CONTEXT_TEXTAREA_MAX_CHARS}
            </span>
          </label>
          {loading ? (
            <p
              className="muted small operator-explain-panel__status"
              role="status"
              aria-live="polite"
            >
              {t("pages.health.aiExplainLoading")}{" "}
              <span className="operator-explain-panel__elapsed">
                ({t("pages.health.aiExplainElapsed", { seconds: elapsedSec })})
              </span>
            </p>
          ) : null}
          <div className="btn-row operator-explain-panel__actions">
            <button
              type="button"
              className="btn-primary"
              onClick={() => void submit()}
              disabled={loading}
            >
              {loading
                ? t("pages.health.aiExplainLoadingShort")
                : t("pages.health.aiExplainSubmit")}
            </button>
            {loading ? (
              <button
                type="button"
                className="btn-secondary"
                onClick={cancelInFlight}
              >
                {t("pages.health.aiExplainCancel")}
              </button>
            ) : null}
            {error && !loading ? (
              <button
                type="button"
                className="btn-secondary"
                onClick={() => void submit()}
              >
                {t("pages.health.aiExplainRetry")}
              </button>
            ) : null}
          </div>
        </div>
      </section>
      {error ? (
        <p className="msg-err operator-explain-panel__error" role="alert">
          {error}
        </p>
      ) : null}
      {error && !loading ? (
        <SurfaceDiagnosticCard
          model={resolveOperatorExplainLlmSurfaceDiagnostic(error)}
        />
      ) : null}
      {showResult && result && envelope ? (
        <div
          className="operator-explain-panel__result"
          role="region"
          aria-label={t("pages.health.aiExplainResultRegion")}
        >
          <LlmStructuredAnswerView
            variant="operator_explain"
            isFakeProvider={envelope.provider === "fake"}
            provider={envelope.provider}
            model={envelope.model}
            cached={envelope.cached === true}
            provenance={envelope.provenance ?? null}
            explanation_de={result.explanation_de}
            referenced_artifacts_de={result.referenced_artifacts_de}
            non_authoritative_note_de={result.non_authoritative_note_de}
            execution_authority={result.execution_authority}
            t={t}
          />
          <div
            className="btn-row operator-explain-panel__actions"
            style={{ marginTop: "1rem" }}
          >
            <button
              type="button"
              className="btn-secondary"
              onClick={() => void submit()}
              disabled={loading}
            >
              {t("pages.health.aiExplainRepeat")}
            </button>
          </div>
        </div>
      ) : null}
      {traceMeta && (traceMeta.rid || traceMeta.cid) ? (
        <details
          className="operator-explain-panel__trace muted small"
          style={{ marginTop: "1rem" }}
        >
          <summary>{t("pages.health.aiExplainTraceTitle")}</summary>
          <p>{t("pages.health.aiExplainTraceBody")}</p>
          {traceMeta.rid ? (
            <p className="mono-small">
              {t("pages.health.aiExplainTraceRequestId")}: {traceMeta.rid}
            </p>
          ) : null}
          {traceMeta.cid && traceMeta.cid !== traceMeta.rid ? (
            <p className="mono-small">
              {t("pages.health.aiExplainTraceCorrelationId")}: {traceMeta.cid}
            </p>
          ) : null}
        </details>
      ) : null}
    </div>
  );
}

export const OperatorExplainPanel = memo(OperatorExplainPanelInner);
