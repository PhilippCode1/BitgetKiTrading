"use client";

import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import {
  SafetyDiagnosisResultView,
  type SafetyDiagnosisResult,
} from "@/components/panels/SafetyDiagnosisResultView";
import {
  OPERATOR_EXPLAIN_CONTEXT_JSON_MAX_BYTES,
  OPERATOR_EXPLAIN_CONTEXT_TEXTAREA_MAX_CHARS,
  readonlyContextJsonUtf8ByteLength,
} from "@/lib/operator-explain-context";
import {
  resolveNetworkFailure,
  resolveOperatorExplainFailure,
  sanitizePublicErrorMessage,
} from "@/lib/operator-explain-errors";
import { isSafetyDiagnosisSuccessPayload } from "@/lib/safety-diagnosis-errors";

const QUESTION_MAX = 8000;
const CLIENT_FETCH_TIMEOUT_MS = 128_000;

type Envelope = Readonly<{
  ok?: boolean;
  provider?: string;
  model?: string;
  cached?: boolean;
  result?: SafetyDiagnosisResult;
  provenance?: Record<string, unknown>;
}>;

function pickInitialQuestion(initial?: string | null): string {
  const v = initial?.trim() ?? "";
  if (v.length >= 3 && v.length <= QUESTION_MAX) return v;
  return "";
}

function SafetyDiagnosisPanelInner({
  bundledContextJson,
  initialQuestionDe,
  embedded,
}: Readonly<{
  bundledContextJson: Record<string, unknown>;
  initialQuestionDe?: string | null;
  embedded: boolean;
}>) {
  const { t } = useI18n();
  const [question, setQuestion] = useState(() =>
    pickInitialQuestion(initialQuestionDe),
  );
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
    const pretty = JSON.stringify(bundledContextJson, null, 2);
    setContextText(pretty);
  }, [bundledContextJson]);

  useEffect(() => {
    const next = pickInitialQuestion(initialQuestionDe);
    if (next.length >= 3) {
      setQuestion((q) => (q.trim().length < 3 ? next : q));
    }
  }, [initialQuestionDe]);

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
      setError(t("pages.health.safetyDiagErrQuestionShort"));
      return;
    }
    if (q.length > QUESTION_MAX) {
      setError(t("pages.health.safetyDiagErrQuestionLong"));
      return;
    }
    let diagnostic_context_json: Record<string, unknown> = {};
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
        diagnostic_context_json = parsed as Record<string, unknown>;
        if (
          readonlyContextJsonUtf8ByteLength(diagnostic_context_json) >
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

    try {
      const res = await fetch("/api/dashboard/llm/safety-incident-diagnose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question_de: q, diagnostic_context_json }),
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
      if (!isSafetyDiagnosisSuccessPayload(parsed)) {
        if (
          parsed !== null &&
          typeof parsed === "object" &&
          !Array.isArray(parsed) &&
          (parsed as Envelope).ok === false
        ) {
          setError(t("pages.health.aiExplainErrUpstreamNotOk"));
          return;
        }
        setError(t("pages.health.safetyDiagErrIncomplete"));
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
  }, [contextText, question, t]);

  const result = envelope?.result;
  const showResult = Boolean(
    result &&
    envelope &&
    envelope.ok !== false &&
    isSafetyDiagnosisSuccessPayload(envelope),
  );
  const isFake =
    (envelope?.provider || "").toLowerCase() === "fake" ||
    (envelope?.model || "").toLowerCase().includes("fake");

  const contextRows = embedded ? 6 : 10;
  const rootClass = embedded
    ? "operator-explain-panel safety-diag-panel safety-diag-panel--embedded"
    : "panel operator-explain-panel safety-diag-panel";

  return (
    <div className={rootClass}>
      {embedded ? (
        <p className="muted small">
          {t("diagnostic.surfaces.common.embeddedSafetyLead")}
        </p>
      ) : (
        <>
          <h2>{t("pages.health.safetyDiagTitle")}</h2>
          <p className="muted small">{t("pages.health.safetyDiagLead")}</p>
          <p className="muted small">{t("pages.health.safetyDiagBoundary")}</p>
        </>
      )}
      <section
        aria-busy={loading}
        aria-label={t("pages.health.safetyDiagFormAria")}
        style={{ marginTop: embedded ? "0.35rem" : "0.75rem" }}
      >
        <div className="operator-explain-panel__fields">
          <label className="small operator-explain-panel__label">
            <span className="muted">
              {t("pages.health.safetyDiagQuestionLabel")}
            </span>
            <textarea
              className="operator-explain-panel__textarea"
              rows={embedded ? 2 : 3}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={t("pages.health.safetyDiagQuestionPlaceholder")}
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
              {t("pages.health.safetyDiagContextLabel")}
            </span>
            <span className="muted small operator-explain-panel__hint">
              {t("pages.health.safetyDiagContextHint")}
            </span>
            <textarea
              className="operator-explain-panel__textarea operator-explain-panel__textarea--mono"
              rows={contextRows}
              value={contextText}
              onChange={(e) => setContextText(e.target.value)}
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
                : t("pages.health.safetyDiagSubmit")}
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
          </div>
          {error ? (
            <p className="msg-err operator-explain-panel__error" role="alert">
              {t("pages.health.aiExplainErrPrefix")} {error}
            </p>
          ) : null}
        </div>
      </section>
      {showResult && result ? (
        <section
          className="operator-explain-panel__result"
          aria-label={t("pages.health.safetyDiagResultAria")}
          style={{ marginTop: "1rem" }}
        >
          <SafetyDiagnosisResultView
            result={result}
            isFakeProvider={isFake}
            provider={envelope?.provider}
            model={envelope?.model}
            provenance={envelope?.provenance ?? null}
            t={t}
          />
          {traceMeta?.rid || traceMeta?.cid ? (
            <p className="muted small" style={{ marginTop: 12 }}>
              {t("pages.health.aiExplainTraceRequestId")}:{" "}
              {traceMeta.rid ?? "—"} ·{" "}
              {t("pages.health.aiExplainTraceCorrelationId")}:{" "}
              {traceMeta.cid ?? "—"}
            </p>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

export const SafetyDiagnosisPanel = memo(function SafetyDiagnosisPanel({
  bundledContextJson,
  contextOverlay,
  initialQuestionDe,
  embedded = false,
}: Readonly<{
  bundledContextJson: Record<string, unknown>;
  contextOverlay?: Record<string, unknown>;
  initialQuestionDe?: string | null;
  embedded?: boolean;
}>) {
  const merged = useMemo(() => {
    if (!contextOverlay || Object.keys(contextOverlay).length === 0) {
      return bundledContextJson;
    }
    return {
      ...bundledContextJson,
      surface_diagnostic_overlay: contextOverlay,
    };
  }, [bundledContextJson, contextOverlay]);
  return (
    <SafetyDiagnosisPanelInner
      bundledContextJson={merged}
      initialQuestionDe={initialQuestionDe ?? undefined}
      embedded={embedded === true}
    />
  );
});
