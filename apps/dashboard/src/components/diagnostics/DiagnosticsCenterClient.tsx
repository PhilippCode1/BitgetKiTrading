"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { SituationAiExplainPanel } from "@/components/diagnostics/SituationAiExplainPanel";
import { useI18n } from "@/components/i18n/I18nProvider";
import {
  crossCuttingIncidents,
  formatDiagnosticMarkdownReport,
  rowMatchesFilter,
  sortComponentsByBusinessPriority,
  businessTierForComponentId,
  type DiagnosticFilterId,
} from "@/lib/diagnostics/diagnostics-view-model";
import { snapshotWarrantsSituationExplain } from "@/lib/situation-explain/build-deterministic";
import { consolePath } from "@/lib/console-paths";
import {
  loadSelfHealingHistory,
  saveSelfHealingHistory,
  SELF_HEALING_HISTORY_MAX,
} from "@/lib/self-healing/history-storage";
import type {
  SelfHealingComponentRow,
  SelfHealingHealingHint,
  SelfHealingHistoryEntry,
  SelfHealingSnapshot,
} from "@/lib/self-healing/schema";

function statusClass(s: string): string {
  switch (s) {
    case "ok":
      return "diagnostics-st diagnostics-st--ok";
    case "degraded":
      return "diagnostics-st diagnostics-st--degraded";
    case "down":
      return "diagnostics-st diagnostics-st--down";
    case "not_configured":
      return "diagnostics-st diagnostics-st--nc";
    default:
      return "diagnostics-st diagnostics-st--unk";
  }
}

function fmtTs(ms: number): string {
  try {
    return new Date(ms).toLocaleString();
  } catch {
    return String(ms);
  }
}

const FILTER_IDS: DiagnosticFilterId[] = [
  "critical_only",
  "unresolved_only",
  "live_relevant",
  "data_only",
  "broker_auth",
];

export function DiagnosticsCenterClient() {
  const { t } = useI18n();
  const [snap, setSnap] = useState<SelfHealingSnapshot | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<Set<DiagnosticFilterId>>(new Set());
  const [history, setHistory] = useState<SelfHealingHistoryEntry[]>([]);
  const [copyOk, setCopyOk] = useState(false);

  const appendHistory = useCallback((e: SelfHealingHistoryEntry) => {
    setHistory((prev) => {
      const next = [e, ...prev].slice(0, SELF_HEALING_HISTORY_MAX);
      saveSelfHealingHistory(next);
      return next;
    });
  }, []);

  const load = useCallback(
    async (recordHistory: boolean) => {
      setLoading(true);
      setErr(null);
      try {
        const res = await fetch("/api/dashboard/self-healing/snapshot", {
          cache: "no-store",
          credentials: "same-origin",
        });
        if (!res.ok) {
          const tx = await res.text();
          throw new Error(tx.slice(0, 400) || `HTTP ${res.status}`);
        }
        const j = (await res.json()) as SelfHealingSnapshot;
        setSnap(j);
        if (recordHistory) {
          appendHistory({
            ts_ms: Date.now(),
            kind: "snapshot",
            summary: t("pages.diagnostics.historySnapshot", {
              n: j.components.length,
            }),
          });
        }
      } catch (e) {
        setErr(e instanceof Error ? e.message : "load_failed");
      } finally {
        setLoading(false);
      }
    },
    [appendHistory, t],
  );

  useEffect(() => {
    setHistory(loadSelfHealingHistory());
  }, []);

  useEffect(() => {
    void load(false);
  }, [load]);

  const rowLabels = useMemo(() => {
    const m: Record<string, string> = {};
    if (!snap) return m;
    for (const c of snap.components) {
      m[c.id] = t(c.labelKey);
    }
    return m;
  }, [snap, t]);

  const filteredRows = useMemo(() => {
    if (!snap) return [];
    const list = sortComponentsByBusinessPriority(snap.components);
    if (filters.size === 0) return list;
    return list.filter((r) => rowMatchesFilter(r, filters));
  }, [snap, filters]);

  const extraIncidents = useMemo(
    () => (snap ? crossCuttingIncidents(snap.incidents) : []),
    [snap],
  );

  const exportMd = useCallback(() => {
    if (!snap) return "";
    return formatDiagnosticMarkdownReport({ snap, rowLabels, t });
  }, [snap, rowLabels, t]);

  const copySummary = useCallback(async () => {
    const md = exportMd();
    if (!md) return;
    try {
      await navigator.clipboard.writeText(md);
      setCopyOk(true);
      setTimeout(() => setCopyOk(false), 2400);
    } catch {
      setErr(t("pages.diagnostics.copyFailed"));
    }
  }, [exportMd, t]);

  const downloadMd = useCallback(() => {
    const md = exportMd();
    if (!md) return;
    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const u = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = u;
    a.download = `diagnose-${new Date().toISOString().slice(0, 19)}.md`;
    a.click();
    URL.revokeObjectURL(u);
  }, [exportMd]);

  const toggleFilter = (id: DiagnosticFilterId) => {
    setFilters((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  };

  const narrative = snap?.narrative_facts;
  const healingHints: readonly SelfHealingHealingHint[] =
    snap?.healing_hints ?? [];

  return (
    <div className="diagnostics-center">
      <section className="panel diagnostics-center__summary" aria-labelledby="diag-summary-h">
        <h2 id="diag-summary-h">{t("pages.diagnostics.sectionSummary")}</h2>
        <p className="muted small">{t("pages.diagnostics.summaryLead")}</p>
        {loading ? (
          <p className="muted" role="status">
            {t("pages.diagnostics.loading")}
          </p>
        ) : null}
        {err ? (
          <p className="msg-err" role="alert">
            {err}
          </p>
        ) : null}
        {snap ? (
          <ul className="diagnostics-summary-list muted small">
            <li>
              {t("pages.diagnostics.summaryCollected", {
                ts: fmtTs(snap.collected_at_ms),
              })}
            </li>
            {snap.support_reference ? (
              <li>
                {t("pages.diagnostics.summaryRef", {
                  ref: snap.support_reference,
                })}
              </li>
            ) : null}
            {narrative ? (
              <li>
                {t("pages.diagnostics.summaryCounts", {
                  ok: narrative.healthyCount,
                  deg: narrative.degradedCount,
                  down: narrative.downCount,
                  inc: narrative.openIncidentCount,
                })}
              </li>
            ) : null}
            {snap.edge_blocks_v1_reads ? (
              <li>{t("pages.diagnostics.summaryEdgeBlocks")}</li>
            ) : null}
          </ul>
        ) : null}
        <div className="diagnostics-toolbar">
          <button
            type="button"
            className="public-btn primary"
            disabled={loading}
            onClick={() => void load(true)}
          >
            {t("pages.diagnostics.btnRefresh")}
          </button>
          <button
            type="button"
            className="public-btn ghost"
            disabled={!snap}
            onClick={() => void copySummary()}
          >
            {copyOk
              ? t("pages.diagnostics.btnCopied")
              : t("pages.diagnostics.btnCopy")}
          </button>
          <button
            type="button"
            className="public-btn ghost"
            disabled={!snap}
            onClick={downloadMd}
          >
            {t("pages.diagnostics.btnDownload")}
          </button>
          <Link href={consolePath("self-healing")} className="public-btn ghost">
            {t("pages.diagnostics.linkSelfHealing")}
          </Link>
          <Link href={consolePath("health")} className="public-btn ghost">
            {t("pages.diagnostics.linkHealth")}
          </Link>
          <a
            href="/api/dashboard/edge-status"
            target="_blank"
            rel="noreferrer"
            className="public-btn ghost"
          >
            {t("pages.diagnostics.linkEdge")}
          </a>
        </div>
      </section>

      {snap && snapshotWarrantsSituationExplain(snap) ? (
        <div className="panel diagnostics-center__situation-explain">
          <SituationAiExplainPanel variant="snapshot" snapshot={snap} />
        </div>
      ) : null}

      <section className="panel diagnostics-center__filters" aria-labelledby="diag-filters-h">
        <h2 id="diag-filters-h">{t("pages.diagnostics.sectionFilters")}</h2>
        <p className="muted small">{t("pages.diagnostics.filtersLead")}</p>
        <div className="diagnostics-filter-chips" role="group">
          {FILTER_IDS.map((id) => (
            <button
              key={id}
              type="button"
              className={`diagnostics-filter-chip${filters.has(id) ? " diagnostics-filter-chip--on" : ""}`}
              aria-pressed={filters.has(id)}
              onClick={() => toggleFilter(id)}
            >
              {t(`pages.diagnostics.filter.${id}`)}
            </button>
          ))}
        </div>
      </section>

      <section className="panel diagnostics-center__table" aria-labelledby="diag-table-h">
        <h2 id="diag-table-h">{t("pages.diagnostics.sectionChecks")}</h2>
        <p className="muted small">{t("pages.diagnostics.checksLead")}</p>
        <div className="diagnostics-table-wrap">
          <table className="data-table diagnostics-table">
            <thead>
              <tr>
                <th>{t("pages.diagnostics.colPriority")}</th>
                <th>{t("pages.diagnostics.colName")}</th>
                <th>{t("pages.diagnostics.colCategory")}</th>
                <th>{t("pages.diagnostics.colStatus")}</th>
                <th>{t("pages.diagnostics.colChecked")}</th>
                <th>{t("pages.diagnostics.colProblem")}</th>
                <th>{t("pages.diagnostics.colCause")}</th>
                <th>{t("pages.diagnostics.colImpact")}</th>
                <th>{t("pages.diagnostics.colAction")}</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((r) => (
                <DiagnosticsComponentRow
                  key={r.id}
                  row={r}
                  name={rowLabels[r.id] ?? r.id}
                  t={t}
                />
              ))}
            </tbody>
          </table>
        </div>
        {snap && filteredRows.length === 0 ? (
          <p className="muted small" role="status">
            {t("pages.diagnostics.emptyFiltered")}
          </p>
        ) : null}
      </section>

      <section className="panel diagnostics-center__incidents" aria-labelledby="diag-inc-h">
        <h2 id="diag-inc-h">{t("pages.diagnostics.sectionCrossIncidents")}</h2>
        <p className="muted small">{t("pages.diagnostics.crossLead")}</p>
        {extraIncidents.length === 0 ? (
          <p className="muted small">{t("pages.diagnostics.crossEmpty")}</p>
        ) : (
          <ul className="diagnostics-incident-list">
            {extraIncidents.map((i) => (
              <li key={i.id} className="diagnostics-incident-card">
                <strong>{i.headline}</strong>
                <span className={`diagnostics-sev diagnostics-sev--${i.severity}`}>
                  {i.severity}
                </span>
                <p className="muted small">{i.suspectedCause}</p>
                <p className="muted small">
                  <strong>{t("pages.diagnostics.colImpact")}:</strong> {i.impact}
                </p>
                <p className="muted small">
                  <strong>{t("pages.diagnostics.colAction")}:</strong> {i.nextStep}
                </p>
                <details className="diagnostics-tech">
                  <summary>{t("pages.diagnostics.technical")}</summary>
                  <pre className="diagnostics-pre">{i.technicalDetail}</pre>
                </details>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel diagnostics-center__healing" aria-labelledby="diag-heal-h">
        <h2 id="diag-heal-h">{t("pages.diagnostics.sectionHealing")}</h2>
        <p className="muted small">{t("pages.diagnostics.healingLead")}</p>
        {healingHints.length === 0 ? (
          <p className="muted small">{t("pages.diagnostics.healingEmpty")}</p>
        ) : (
          <ul className="diagnostics-hint-list">
            {healingHints.map((h) => (
              <li key={h.id}>
                {t(h.messageKey)}
                {h.sinceMs ? (
                  <span className="muted small"> · {fmtTs(h.sinceMs)}</span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel diagnostics-center__history" aria-labelledby="diag-hist-h">
        <h2 id="diag-hist-h">{t("pages.diagnostics.sectionHistory")}</h2>
        <p className="muted small">{t("pages.diagnostics.historyLead")}</p>
        <p className="muted small">{t("pages.diagnostics.historyShared")}</p>
        {history.length === 0 ? (
          <p className="muted small">{t("pages.diagnostics.historyEmpty")}</p>
        ) : (
          <ul className="diagnostics-history-list">
            {history.map((h, idx) => (
              <li key={`${h.ts_ms}-${idx}`}>
                <span className="mono-small">{fmtTs(h.ts_ms)}</span> —{" "}
                <span className="diagnostics-history-kind">{h.kind}</span>:{" "}
                {h.summary}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function DiagnosticsComponentRow({
  row,
  name,
  t,
}: {
  row: SelfHealingComponentRow;
  name: string;
  t: (k: string, v?: Record<string, string | number | boolean>) => string;
}) {
  const tier = businessTierForComponentId(row.id);
  const tech = row.technicalDetail?.trim() ?? "";
  const causeSnippet =
    row.status === "ok"
      ? t("pages.diagnostics.causeOkShort")
      : tech.length > 0
        ? tech.length > 220
          ? `${tech.slice(0, 220)}…`
          : tech
        : t("pages.diagnostics.causeNoTech");
  return (
    <tr>
      <td className="mono-small">P{tier + 1}</td>
      <td>
        <strong>{name}</strong>
        {row.manualRemediationRequired ? (
          <span className="diagnostics-manual">{t("pages.diagnostics.manualBadge")}</span>
        ) : null}
      </td>
      <td className="muted small">{t(row.categoryKey)}</td>
      <td>
        <span className={statusClass(row.status)}>{row.status}</span>
      </td>
      <td className="mono-small muted">{fmtTs(row.lastSeenMs)}</td>
      <td className="small">{row.suspectedCause}</td>
      <td className="small muted diagnostics-td--cause">
        {causeSnippet}
      </td>
      <td className="small">{row.impact}</td>
      <td className="small">
        {row.nextStep}
        {row.autoRemediations.length > 0 ? (
          <ul className="diagnostics-mini-list">
            {row.autoRemediations.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        ) : null}
        <details className="diagnostics-tech">
          <summary>{t("pages.diagnostics.technical")}</summary>
          <pre className="diagnostics-pre">{row.technicalDetail}</pre>
        </details>
      </td>
    </tr>
  );
}
