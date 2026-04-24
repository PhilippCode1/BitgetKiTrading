"use client";

import { memo, useCallback, useEffect, useRef, useState } from "react";

import { ConsoleFetchNotice } from "@/components/console/ConsoleFetchNotice";
import { useI18n } from "@/components/i18n/I18nProvider";
import {
  resolveNetworkFailure,
  resolveOperatorExplainFailure,
  sanitizePublicErrorMessage,
} from "@/lib/operator-explain-errors";

const CLIENT_FETCH_TIMEOUT_MS = 128_000;
const MESSAGE_MAX = 8000;

const EXEC_UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function newConversationId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `conv-${Date.now()}`;
}

export type AssistSegmentDef = Readonly<{
  segment: string;
  labelKey: string;
  /** i18n-Key: erlaubte context_json-Top-Level-Keys fuer dieses Segment */
  contextHintKey: string;
}>;

type AssistLayerPanelProps = Readonly<{
  segments: AssistSegmentDef[];
  titleKey: string;
  leadKey: string;
  /** Tab „ops-risk“: execution_id → Forensik-Kontext (Golden Record + Policy) */
  enableOpsRiskForensicLoader?: boolean;
}>;

type Turn = Readonly<{ user: string; assistant: string }>;

function AssistLayerPanelInner({
  segments,
  titleKey,
  leadKey,
  enableOpsRiskForensicLoader = false,
}: AssistLayerPanelProps) {
  const { t } = useI18n();
  const [activeSegment, setActiveSegment] = useState(
    segments[0]?.segment ?? "admin-operations",
  );
  const [conversationId, setConversationId] = useState(newConversationId);
  const [message, setMessage] = useState("");
  const [contextText, setContextText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [lastMeta, setLastMeta] = useState<{
    provider?: string;
    model?: string;
    historyCount?: number;
    fake?: boolean;
  } | null>(null);
  const [executionIdForRisk, setExecutionIdForRisk] = useState("");
  const [loadingContext, setLoadingContext] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);
  const segmentInitRef = useRef(true);

  const activeHintKey =
    segments.find((s) => s.segment === activeSegment)?.contextHintKey ??
    "pages.health.assistContextHintGeneric";

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      abortRef.current?.abort();
    };
  }, []);

  /** Tab-Wechsel: neuer Verlauf und neue ID — verhindert Vermischung mit anderem Segment. */
  useEffect(() => {
    if (segmentInitRef.current) {
      segmentInitRef.current = false;
      return;
    }
    abortRef.current?.abort();
    setConversationId(newConversationId());
    setTurns([]);
    setLastMeta(null);
    setError(null);
    setMessage("");
    setContextText("");
    setExecutionIdForRisk("");
  }, [activeSegment]);

  const newConversation = useCallback(() => {
    abortRef.current?.abort();
    setConversationId(newConversationId());
    setTurns([]);
    setLastMeta(null);
    setError(null);
  }, []);

  const loadOpsRiskForensicContext = useCallback(async () => {
    if (!enableOpsRiskForensicLoader) return;
    setError(null);
    const eid = executionIdForRisk.trim();
    if (!eid) {
      setError(t("pages.health.assistOpsRiskLoadErr"));
      return;
    }
    if (!EXEC_UUID_RE.test(eid)) {
      setError(t("pages.health.assistOpsRiskLoadErr"));
      return;
    }
    setLoadingContext(true);
    try {
      const res = await fetch(
        `/api/dashboard/live-broker/executions/${encodeURIComponent(eid)}/ops-risk-assist-context`,
        { method: "GET" },
      );
      const text = await res.text();
      if (!mountedRef.current) return;
      if (!res.ok) {
        setError(t("pages.health.assistOpsRiskLoadErr"));
        return;
      }
      let data: Record<string, unknown>;
      try {
        data = JSON.parse(text) as Record<string, unknown>;
      } catch {
        setError(t("pages.health.aiExplainErrBadJson"));
        return;
      }
      const golden = data.trade_lifecycle_golden;
      const inq = data.risk_rejection_inquiry;
      const brief = data.decision_brief;
      if (
        golden === undefined ||
        typeof golden !== "object" ||
        golden === null
      ) {
        setError(t("pages.health.assistOpsRiskLoadErr"));
        return;
      }
      const out: Record<string, unknown> = {
        decision_brief: brief ?? {},
        trade_lifecycle_golden: golden,
        risk_rejection_inquiry: inq ?? {},
      };
      setContextText(JSON.stringify(out, null, 2));
    } catch (e) {
      if (mountedRef.current) setError(resolveNetworkFailure(e, t));
    } finally {
      if (mountedRef.current) setLoadingContext(false);
    }
  }, [enableOpsRiskForensicLoader, executionIdForRisk, t]);

  const submit = useCallback(async () => {
    setError(null);
    const msg = message.trim();
    if (msg.length < 3) {
      setError(t("pages.health.assistErrMessageShort"));
      return;
    }
    if (msg.length > MESSAGE_MAX) {
      setError(t("pages.health.assistErrMessageLong"));
      return;
    }
    let context_json: Record<string, unknown> = {};
    const raw = contextText.trim();
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
        context_json = parsed as Record<string, unknown>;
      } catch {
        setError(t("pages.health.aiExplainErrContextJson"));
        return;
      }
    }

    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    const timer = window.setTimeout(() => ac.abort(), CLIENT_FETCH_TIMEOUT_MS);
    setLoading(true);
    try {
      const res = await fetch(`/api/dashboard/llm/assist/${activeSegment}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: conversationId,
          user_message_de: msg,
          context_json,
        }),
        signal: ac.signal,
      });
      const text = await res.text();
      if (!mountedRef.current) return;
      if (!res.ok) {
        setError(resolveOperatorExplainFailure(res.status, text, t));
        return;
      }
      let data: Record<string, unknown>;
      try {
        data = JSON.parse(text) as Record<string, unknown>;
      } catch {
        setError(t("pages.health.aiExplainErrBadJson"));
        return;
      }
      if (data.ok !== true) {
        setError(t("pages.health.aiExplainErrUpstreamNotOk"));
        return;
      }
      const result = data.result as Record<string, unknown> | undefined;
      const reply =
        result && typeof result.assistant_reply_de === "string"
          ? result.assistant_reply_de.trim()
          : "";
      if (!reply) {
        setError(t("pages.health.assistErrEmptyReply"));
        return;
      }
      const sess = data.assist_session as Record<string, unknown> | undefined;
      const histCount =
        typeof sess?.history_message_count === "number"
          ? sess.history_message_count
          : undefined;
      setTurns((prev) => [...prev, { user: msg, assistant: reply }]);
      setLastMeta({
        provider: typeof data.provider === "string" ? data.provider : undefined,
        model: typeof data.model === "string" ? data.model : undefined,
        historyCount: histCount,
        fake: data.provider === "fake",
      });
      setMessage("");
    } catch (e) {
      if (!mountedRef.current) return;
      if (e instanceof DOMException && e.name === "AbortError") {
        setError(t("pages.health.aiExplainErrAborted"));
        return;
      }
      setError(resolveNetworkFailure(e, t));
    } finally {
      window.clearTimeout(timer);
      if (mountedRef.current) setLoading(false);
    }
  }, [activeSegment, contextText, conversationId, message, t]);

  const activeLabelKey =
    segments.find((s) => s.segment === activeSegment)?.labelKey ?? "";

  return (
    <div className="panel" aria-labelledby="assist-layer-heading">
      <h2 id="assist-layer-heading">{t(titleKey)}</h2>
      <p className="muted small">{t(leadKey)}</p>
      <p className="muted small">{t("pages.health.assistSegmentScopeNote")}</p>
      <p className="muted small">
        {t("pages.health.assistConversationHint")}{" "}
        <span className="mono-small">{conversationId.slice(0, 8)}…</span>{" "}
        <button type="button" className="link-button" onClick={newConversation}>
          {t("pages.health.assistNewConversation")}
        </button>
      </p>
      <div
        style={{
          display: "flex",
          gap: "0.5rem",
          flexWrap: "wrap",
          marginBottom: "1rem",
        }}
        role="tablist"
        aria-label={t("pages.health.assistTabsAria")}
      >
        {segments.map((s) => (
          <button
            key={s.segment}
            type="button"
            role="tab"
            aria-selected={activeSegment === s.segment}
            className={activeSegment === s.segment ? "primary" : "secondary"}
            onClick={() => {
              setActiveSegment(s.segment);
              setError(null);
            }}
          >
            {t(s.labelKey)}
          </button>
        ))}
      </div>
      <label className="block-label">
        <span>{t("pages.health.assistMessageLabel")}</span>
        <textarea
          className="console-textarea"
          rows={4}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          maxLength={MESSAGE_MAX}
          disabled={loading}
          placeholder={t("pages.health.assistMessagePlaceholder")}
        />
      </label>
      {enableOpsRiskForensicLoader && activeSegment === "ops-risk" ? (
        <div className="block-label" style={{ marginBottom: "0.75rem" }}>
          <span>{t("pages.health.assistOpsRiskLoadLabel")}</span>
          <p className="muted small">{t("pages.health.assistOpsRiskLoadHelp")}</p>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "0.5rem",
              alignItems: "center",
              marginTop: 6,
            }}
          >
            <input
              type="text"
              className="console-textarea mono-small"
              style={{ minWidth: 280, maxWidth: "100%", padding: "0.4rem 0.5rem" }}
              value={executionIdForRisk}
              onChange={(e) => setExecutionIdForRisk(e.target.value)}
              disabled={loading || loadingContext}
              autoComplete="off"
              spellCheck={false}
              placeholder="00000000-0000-4000-8000-000000000000"
            />
            <button
              type="button"
              className="secondary"
              onClick={() => void loadOpsRiskForensicContext()}
              disabled={loading || loadingContext}
            >
              {loadingContext
                ? t("pages.health.aiExplainLoadingShort")
                : t("pages.health.assistOpsRiskLoadButton")}
            </button>
          </div>
        </div>
      ) : null}
      <label className="block-label">
        <span>{t("pages.health.assistContextLabel")}</span>
        <span className="muted small block">{t(activeHintKey)}</span>
        <textarea
          className="console-textarea mono-small"
          rows={5}
          value={contextText}
          onChange={(e) => setContextText(e.target.value)}
          disabled={loading}
          placeholder={t("pages.health.assistContextPlaceholder")}
        />
      </label>
      <div className="form-actions">
        <button
          type="button"
          className="primary"
          onClick={() => void submit()}
          disabled={loading}
        >
          {loading
            ? t("pages.health.aiExplainLoadingShort")
            : t("pages.health.assistSubmit")}
        </button>
      </div>
      {turns.length === 0 && !loading && !error ? (
        <ConsoleFetchNotice
          variant="soft"
          title={t("ui.surfaceState.assist.emptyTitle")}
          body={t("ui.surfaceState.assist.emptyBody")}
          refreshHint={t("ui.surfaceState.assist.emptyRefreshHint")}
          showStateActions
        />
      ) : null}
      {error ? (
        <ConsoleFetchNotice
          variant="alert"
          title={t("ui.surfaceState.assist.callFailedTitle")}
          body={sanitizePublicErrorMessage(
            `${t("pages.health.aiExplainErrPrefix")} ${error}`,
          )}
          refreshHint={t("ui.refreshHint")}
          showStateActions
          wrapActions
        />
      ) : null}
      {lastMeta?.fake ? (
        <p className="warning-banner small" role="status">
          {t("pages.health.aiExplainFakeBanner")}
        </p>
      ) : null}
      {lastMeta ? (
        <p className="muted small">
          {t("pages.health.aiExplainProvider")}: {lastMeta.provider ?? "—"} ·{" "}
          {lastMeta.model ?? "—"}
          {lastMeta.historyCount != null
            ? ` · ${t("pages.health.assistHistoryCount", { count: lastMeta.historyCount })}`
            : null}
        </p>
      ) : null}
      {turns.length > 0 ? (
        <div
          className="assist-transcript"
          aria-label={t("pages.health.assistTranscriptAria")}
        >
          <h3 className="h3-quiet">
            {t("pages.health.assistTranscriptTitle")}
          </h3>
          {activeLabelKey ? (
            <p className="muted small assist-transcript__segment">
              {t("pages.health.assistTranscriptSegmentLabel")}:{" "}
              {t(activeLabelKey)}
            </p>
          ) : null}
          <ul className="news-list">
            {turns.map((row, i) => (
              <li key={i}>
                <strong>{t("pages.health.assistYou")}</strong> {row.user}
                <br />
                <strong>{t("pages.health.assistAssistant")}</strong>{" "}
                {row.assistant}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <p className="muted small">{t("pages.health.assistSeparationNote")}</p>
    </div>
  );
}

export const AssistLayerPanel = memo(AssistLayerPanelInner);
