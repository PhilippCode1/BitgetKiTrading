"use client";

import { memo, useCallback, useEffect, useRef, useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import { LlmStructuredAnswerView } from "@/components/panels/LlmStructuredAnswerView";
import { useSignalDetailLlmChartOptional } from "@/components/signals/signal-detail-llm-chart-context";
import {
  isStrategySignalExplainSuccessPayload,
  resolveNetworkFailure,
  resolveStrategySignalExplainFailure,
  sanitizePublicErrorMessage,
} from "@/lib/strategy-signal-explain-errors";

const FOCUS_MAX = 8000;
const CLIENT_FETCH_TIMEOUT_MS = 128_000;

type StrategyResult = {
  schema_version?: string;
  execution_authority?: string;
  strategy_explanation_de?: string;
  risk_and_caveats_de?: string;
  referenced_input_keys_de?: string[];
  non_authoritative_note_de?: string;
  chart_annotations?: unknown;
};

type Envelope = {
  ok?: boolean;
  provider?: string;
  model?: string;
  cached?: boolean;
  result?: StrategyResult;
  provenance?: Record<string, unknown>;
};

type Props = Readonly<{
  /** Readonly-Snapshot aus Gateway (Signal-Detail), serverseitig serialisiert. */
  signalContextJson: Record<string, unknown>;
}>;

function StrategySignalExplainPanelInner({ signalContextJson }: Props) {
  const { t } = useI18n();
  const signalLlmChart = useSignalDetailLlmChartOptional();
  const [focus, setFocus] = useState("");
  const [loading, setLoading] = useState(false);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [envelope, setEnvelope] = useState<Envelope | null>(null);

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
    const fq = focus.trim();
    if (fq.length > FOCUS_MAX) {
      setError(t("pages.health.aiExplainErrQuestionLong"));
      return;
    }
    const keyCount = Object.keys(signalContextJson).length;
    if (keyCount === 0 && fq.length < 3) {
      setError(t("pages.signalsDetail.aiStrategyErrNeedContextOrFocus"));
      return;
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
    setLoading(true);
    signalLlmChart?.setAnnotationsRaw(null);
    signalLlmChart?.setRationaleDe(null);

    const payload: Record<string, unknown> = {
      signal_context_json: signalContextJson,
    };
    if (fq.length >= 3) {
      payload.focus_question_de = fq;
    }

    try {
      const res = await fetch("/api/dashboard/llm/strategy-signal-explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        cache: "no-store",
        signal: ac.signal,
      });
      const text = await res.text();
      if (!mountedRef.current) {
        return;
      }
      if (!res.ok) {
        setError(resolveStrategySignalExplainFailure(res.status, text, t));
        return;
      }
      let parsed: unknown;
      try {
        parsed = JSON.parse(text) as unknown;
      } catch {
        setError(t("pages.health.aiExplainErrBadJson"));
        return;
      }
      if (!isStrategySignalExplainSuccessPayload(parsed)) {
        if (
          parsed !== null &&
          typeof parsed === "object" &&
          !Array.isArray(parsed) &&
          (parsed as Envelope).ok === false
        ) {
          setError(t("pages.health.aiExplainErrUpstreamNotOk"));
          return;
        }
        setError(t("pages.signalsDetail.aiStrategyErrIncompleteResponse"));
        return;
      }
      setEnvelope(parsed as Envelope);
      const env = parsed as Envelope;
      const r = env.result;
      if (
        signalLlmChart &&
        r !== null &&
        typeof r === "object" &&
        !Array.isArray(r)
      ) {
        const ca = (r as Record<string, unknown>).chart_annotations;
        signalLlmChart.setAnnotationsRaw(ca !== undefined ? ca : null);
        const expl = (r as StrategyResult).strategy_explanation_de;
        signalLlmChart.setRationaleDe(
          typeof expl === "string" && expl.trim() ? expl.trim() : null,
        );
      }
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
  }, [focus, signalContextJson, signalLlmChart, t]);

  const result = envelope?.result;
  const showResult = Boolean(
    result &&
    envelope &&
    envelope.ok !== false &&
    isStrategySignalExplainSuccessPayload(envelope),
  );
  return (
    <div className="panel operator-explain-panel strategy-signal-explain-panel">
      <h2>{t("pages.signalsDetail.aiStrategyTitle")}</h2>
      <p className="muted small">{t("pages.signalsDetail.aiStrategyLead")}</p>
      <p className="muted small">
        {t("pages.signalsDetail.aiStrategySnapshotNote")}
      </p>
      <p className="muted small">
        {t("pages.signalsDetail.aiStrategyChartHint")}
      </p>
      <section
        aria-busy={loading}
        aria-label={t("pages.signalsDetail.aiStrategyFormAria")}
        style={{ marginTop: "0.75rem" }}
      >
        <div className="operator-explain-panel__fields">
          <label className="small operator-explain-panel__label">
            <span className="muted">
              {t("pages.signalsDetail.aiStrategyFocusLabel")}
            </span>
            <textarea
              className="operator-explain-panel__textarea"
              rows={2}
              value={focus}
              onChange={(e) => setFocus(e.target.value)}
              placeholder={t("pages.signalsDetail.aiStrategyFocusPlaceholder")}
              disabled={loading}
              autoComplete="off"
              maxLength={FOCUS_MAX}
            />
            <span className="muted small operator-explain-panel__counter">
              {focus.length}/{FOCUS_MAX}
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
                : t("pages.signalsDetail.aiStrategySubmit")}
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
      {showResult && result && envelope ? (
        <div
          className="operator-explain-panel__result"
          role="region"
          aria-label={t("pages.signalsDetail.aiStrategyResultAria")}
        >
          <LlmStructuredAnswerView
            variant="strategy_signal_explain"
            isFakeProvider={envelope.provider === "fake"}
            provider={envelope.provider}
            model={envelope.model}
            cached={envelope.cached === true}
            provenance={envelope.provenance ?? null}
            strategy_explanation_de={result.strategy_explanation_de}
            risk_and_caveats_de={result.risk_and_caveats_de}
            referenced_input_keys_de={result.referenced_input_keys_de}
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
    </div>
  );
}

export const StrategySignalExplainPanel = memo(StrategySignalExplainPanelInner);
