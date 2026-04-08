"use client";

import { memo, useCallback, useEffect, useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import { useSignalDetailLlmChartOptional } from "@/components/signals/signal-detail-llm-chart-context";
import { precheckPromotionRequest } from "@/lib/ai-strategy-proposal-governance";

type DraftListItem = Readonly<{
  draft_id: string;
  created_ts?: string;
  lifecycle_status?: string;
  symbol?: string;
  timeframe?: string;
}>;

type Props = Readonly<{
  signalId: string;
  symbol: string;
  timeframe: string;
  chartContextJson: Record<string, unknown>;
}>;

function StrategyProposalDraftPanelInner({
  signalId,
  symbol,
  timeframe,
  chartContextJson,
}: Props) {
  const { t } = useI18n();
  const llmChart = useSignalDetailLlmChartOptional();
  const [focus, setFocus] = useState("");
  const [loading, setLoading] = useState(false);
  const [listLoading, setListLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<DraftListItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detailStatus, setDetailStatus] = useState<string | null>(null);
  const [humanAck, setHumanAck] = useState(false);
  const [promoTarget, setPromoTarget] = useState<
    "paper_sandbox" | "shadow_observe" | "live_requires_full_gates"
  >("paper_sandbox");

  const reloadList = useCallback(async () => {
    setListLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/dashboard/operator/ai-strategy-proposal-drafts?signal_id=${encodeURIComponent(signalId)}&limit=30`,
        { cache: "no-store" },
      );
      const text = await res.text();
      if (!res.ok) {
        setError(text || `HTTP ${res.status}`);
        setDrafts([]);
        return;
      }
      const j = JSON.parse(text) as {
        items?: DraftListItem[];
        degraded?: boolean;
      };
      setDrafts(Array.isArray(j.items) ? j.items : []);
      if (j.degraded) {
        setError(t("pages.signalsDetail.proposalDraftTableMissingHint"));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t("errors.fallbackMessage"));
      setDrafts([]);
    } finally {
      setListLoading(false);
    }
  }, [signalId, t]);

  useEffect(() => {
    void reloadList();
  }, [reloadList]);

  const generate = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const fq = focus.trim();
      const payload: Record<string, unknown> = {
        chart_context_json: chartContextJson,
        signal_id: signalId,
        symbol,
        timeframe,
      };
      if (fq.length >= 3) payload.focus_question_de = fq;
      const res = await fetch(
        "/api/dashboard/operator/ai-strategy-proposal-drafts",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          cache: "no-store",
        },
      );
      const text = await res.text();
      if (!res.ok) {
        setError(text || `HTTP ${res.status}`);
        return;
      }
      const j = JSON.parse(text) as {
        draft_id?: string;
        result?: { chart_annotations?: unknown };
      };
      if (j.draft_id) setSelectedId(j.draft_id);
      if (j.result?.chart_annotations != null && llmChart) {
        llmChart.setAnnotationsRaw(j.result.chart_annotations);
        llmChart.setLayerEnabled(true);
      }
      await reloadList();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("errors.fallbackMessage"));
    } finally {
      setLoading(false);
    }
  }, [
    chartContextJson,
    focus,
    llmChart,
    reloadList,
    signalId,
    symbol,
    t,
    timeframe,
  ]);

  const applyAnnotations = useCallback(
    async (draftId: string) => {
      setError(null);
      try {
        const res = await fetch(
          `/api/dashboard/operator/ai-strategy-proposal-drafts/${encodeURIComponent(draftId)}`,
          { cache: "no-store" },
        );
        const text = await res.text();
        if (!res.ok) {
          setError(text || `HTTP ${res.status}`);
          return;
        }
        const j = JSON.parse(text) as {
          draft?: { proposal_payload_jsonb?: { chart_annotations?: unknown } };
        };
        const ca = j.draft?.proposal_payload_jsonb?.chart_annotations;
        if (ca != null && llmChart) {
          llmChart.setAnnotationsRaw(ca);
          llmChart.setLayerEnabled(true);
        }
        setSelectedId(draftId);
      } catch (e) {
        setError(e instanceof Error ? e.message : t("errors.fallbackMessage"));
      }
    },
    [llmChart, t],
  );

  const runValidate = useCallback(
    async (draftId: string) => {
      setError(null);
      try {
        const res = await fetch(
          `/api/dashboard/operator/ai-strategy-proposal-drafts/${encodeURIComponent(draftId)}/validate-deterministic`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: "{}",
          },
        );
        const text = await res.text();
        if (!res.ok) {
          setError(text || `HTTP ${res.status}`);
          return;
        }
        await reloadList();
      } catch (e) {
        setError(e instanceof Error ? e.message : t("errors.fallbackMessage"));
      }
    },
    [reloadList, t],
  );

  const requestPromotion = useCallback(
    async (draftId: string, lifecycleStatus: string) => {
      setError(null);
      const pre = precheckPromotionRequest({
        lifecycleStatus,
        humanAcknowledged: humanAck,
      });
      if (!pre.ok) {
        setError(
          pre.code === "HUMAN_ACK_REQUIRED"
            ? t("pages.signalsDetail.proposalDraftErrNeedAck")
            : t("pages.signalsDetail.proposalDraftErrNeedValidation"),
        );
        return;
      }
      try {
        const res = await fetch(
          `/api/dashboard/operator/ai-strategy-proposal-drafts/${encodeURIComponent(draftId)}/request-promotion`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              human_acknowledged: true,
              promotion_target: promoTarget,
            }),
          },
        );
        const text = await res.text();
        if (!res.ok) {
          setError(text || `HTTP ${res.status}`);
          return;
        }
        setDetailStatus("promotion_requested");
        await reloadList();
      } catch (e) {
        setError(e instanceof Error ? e.message : t("errors.fallbackMessage"));
      }
    },
    [humanAck, promoTarget, reloadList, t],
  );

  return (
    <div className="panel operator-explain-panel strategy-proposal-draft-panel">
      <h2>{t("pages.signalsDetail.proposalDraftTitle")}</h2>
      <p className="muted small">
        {t("pages.signalsDetail.proposalDraftLead")}
      </p>
      <p className="muted small">
        {t("pages.signalsDetail.proposalDraftBoundary")}
      </p>
      <label className="small operator-explain-panel__label">
        <span className="muted">
          {t("pages.signalsDetail.proposalDraftFocusLabel")}
        </span>
        <textarea
          className="operator-explain-panel__textarea"
          rows={2}
          value={focus}
          onChange={(e) => setFocus(e.target.value)}
          placeholder={t("pages.signalsDetail.proposalDraftFocusPlaceholder")}
          disabled={loading}
        />
      </label>
      <div className="btn-row operator-explain-panel__actions">
        <button
          type="button"
          className="btn-primary"
          disabled={loading}
          onClick={() => void generate()}
        >
          {loading
            ? t("pages.signalsDetail.proposalDraftGenerating")
            : t("pages.signalsDetail.proposalDraftGenerate")}
        </button>
        <button
          type="button"
          className="btn-secondary"
          disabled={listLoading}
          onClick={() => void reloadList()}
        >
          {t("pages.signalsDetail.proposalDraftReloadList")}
        </button>
      </div>
      {error ? (
        <p className="msg-err" role="alert">
          {error}
        </p>
      ) : null}
      <h3 className="h3-quiet" style={{ marginTop: "1rem" }}>
        {t("pages.signalsDetail.proposalDraftRegistryTitle")}
      </h3>
      {listLoading ? (
        <p className="muted small">
          {t("pages.signalsDetail.proposalDraftListLoading")}
        </p>
      ) : drafts.length === 0 ? (
        <p className="muted small">
          {t("pages.signalsDetail.proposalDraftListEmpty")}
        </p>
      ) : (
        <ul className="news-list">
          {drafts.map((d) => (
            <li key={d.draft_id}>
              <div className="mono-small">{d.draft_id.slice(0, 8)}…</div>
              <div className="muted small">
                {d.lifecycle_status ?? "—"} · {d.created_ts ?? "—"}
              </div>
              <div className="btn-row" style={{ marginTop: 6 }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => void applyAnnotations(d.draft_id)}
                >
                  {t("pages.signalsDetail.proposalDraftApplyChart")}
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => void runValidate(d.draft_id)}
                >
                  {t("pages.signalsDetail.proposalDraftValidate")}
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() =>
                    void requestPromotion(
                      d.draft_id,
                      d.lifecycle_status ?? "draft",
                    )
                  }
                >
                  {t("pages.signalsDetail.proposalDraftRequestPromotion")}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <div style={{ marginTop: "1rem" }}>
        <label
          className="small"
          style={{ display: "flex", gap: 8, alignItems: "center" }}
        >
          <input
            type="checkbox"
            checked={humanAck}
            onChange={(e) => setHumanAck(e.target.checked)}
          />
          <span>{t("pages.signalsDetail.proposalDraftHumanAck")}</span>
        </label>
        <label className="small" style={{ marginTop: 8, display: "block" }}>
          <span className="muted">
            {t("pages.signalsDetail.proposalDraftPromoTarget")}
          </span>
          <select
            value={promoTarget}
            onChange={(e) =>
              setPromoTarget(
                e.target.value as
                  | "paper_sandbox"
                  | "shadow_observe"
                  | "live_requires_full_gates",
              )
            }
            style={{ marginLeft: 8 }}
          >
            <option value="paper_sandbox">
              {t("pages.signalsDetail.proposalDraftTargetPaper")}
            </option>
            <option value="shadow_observe">
              {t("pages.signalsDetail.proposalDraftTargetShadow")}
            </option>
            <option value="live_requires_full_gates">
              {t("pages.signalsDetail.proposalDraftTargetLive")}
            </option>
          </select>
        </label>
        <p className="muted small" style={{ marginTop: 8 }}>
          {t("pages.signalsDetail.proposalDraftPromoFootnote")}
        </p>
        {detailStatus ? (
          <p className="muted small" role="status">
            {detailStatus}
          </p>
        ) : null}
        {selectedId ? (
          <p className="muted small mono-small">
            {t("pages.signalsDetail.proposalDraftSelected")}:{" "}
            {selectedId.slice(0, 8)}…
          </p>
        ) : null}
      </div>
    </div>
  );
}

export const StrategyProposalDraftPanel = memo(StrategyProposalDraftPanelInner);
