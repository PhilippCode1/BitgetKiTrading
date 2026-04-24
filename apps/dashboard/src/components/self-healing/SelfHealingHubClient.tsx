"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { SituationAiExplainPanel } from "@/components/diagnostics/SituationAiExplainPanel";
import { useI18n } from "@/components/i18n/I18nProvider";
import { consolePath } from "@/lib/console-paths";
import {
  loadSelfHealingHistory,
  saveSelfHealingHistory,
  SELF_HEALING_HISTORY_MAX,
} from "@/lib/self-healing/history-storage";
import type {
  SelfHealingHistoryEntry,
  SelfHealingIncident,
  SelfHealingRepairAction,
  SelfHealingSnapshot,
} from "@/lib/self-healing/schema";
import { snapshotWarrantsSituationExplain } from "@/lib/situation-explain/build-deterministic";

function severityClass(s: string): string {
  switch (s) {
    case "blocking":
      return "self-healing-sev self-healing-sev--blocking";
    case "critical":
      return "self-healing-sev self-healing-sev--critical";
    case "warning":
      return "self-healing-sev self-healing-sev--warning";
    case "hint":
      return "self-healing-sev self-healing-sev--hint";
    default:
      return "self-healing-sev self-healing-sev--info";
  }
}

function statusClass(s: string): string {
  switch (s) {
    case "ok":
      return "self-healing-st self-healing-st--ok";
    case "degraded":
      return "self-healing-st self-healing-st--degraded";
    case "down":
      return "self-healing-st self-healing-st--down";
    case "not_configured":
      return "self-healing-st self-healing-st--nc";
    default:
      return "self-healing-st self-healing-st--unk";
  }
}

function repairHandler(
  a: SelfHealingRepairAction,
  router: ReturnType<typeof useRouter>,
): void {
  switch (a.kind) {
    case "reload_dashboard_region":
      router.refresh();
      break;
    case "open_edge_diagnostics":
      window.open("/api/dashboard/edge-status", "_blank", "noopener,noreferrer");
      break;
    case "open_health_page":
      window.location.href = consolePath("health");
      break;
    case "open_live_terminal":
      window.location.href = consolePath("terminal");
      break;
    case "open_integrations":
      window.location.href = consolePath("integrations");
      break;
    default:
      break;
  }
}

export function SelfHealingHubClient() {
  const { t } = useI18n();
  const router = useRouter();
  const [snap, setSnap] = useState<SelfHealingSnapshot | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [repairing, setRepairing] = useState(false);
  const [history, setHistory] = useState<SelfHealingHistoryEntry[]>([]);

  const appendHistory = useCallback((e: SelfHealingHistoryEntry) => {
    setHistory((prev) => {
      const next = [e, ...prev].slice(0, SELF_HEALING_HISTORY_MAX);
      saveSelfHealingHistory(next);
      return next;
    });
  }, []);

  const load = useCallback(
    async (reason: "auto" | "manual" = "manual") => {
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
        if (reason === "manual") {
          appendHistory({
            ts_ms: Date.now(),
            kind: "snapshot",
            summary: t("pages.selfHealing.history.snapshotSummary", {
              n: j.incidents.length,
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
    void load("auto");
  }, [load]);

  const runRepair = useCallback(
    async (action: string, targetId?: string, serviceName?: string) => {
      setRepairing(true);
      setErr(null);
      try {
        const res = await fetch("/api/dashboard/self-healing/action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({
            action,
            target_component_id: targetId ?? null,
            service_name: serviceName ?? null,
          }),
        });
        if (!res.ok) {
          const tx = await res.text();
          throw new Error(tx.slice(0, 400) || `HTTP ${res.status}`);
        }
        const j = (await res.json()) as {
          snapshot: SelfHealingSnapshot;
          action: string;
        };
        setSnap(j.snapshot);
        appendHistory({
          ts_ms: Date.now(),
          kind: "repair_attempt",
          summary: t("pages.selfHealing.history.repairSummary", {
            action: j.action,
          }),
        });
      } catch (e) {
        setErr(e instanceof Error ? e.message : "repair_failed");
      } finally {
        setRepairing(false);
      }
    },
    [appendHistory, t],
  );

  const recoveryTimeline = useMemo(() => {
    const items = snap?.self_healing_items;
    if (!items?.length) return [];
    const flat: { ts_ms: number; line: string; service: string }[] = [];
    for (const it of items) {
      for (const e of it.timeline) {
        const msg = (e as { message?: string }).message ?? (e as { event?: string }).event ?? "event";
        const ev = (e as { event?: string }).event ?? "event";
        flat.push({
          ts_ms: (e as { ts_ms: number }).ts_ms,
          line: `${it.service_name}: ${ev} — ${String(msg).slice(0, 200)}`,
          service: it.service_name,
        });
      }
    }
    flat.sort((a, b) => b.ts_ms - a.ts_ms);
    return flat;
  }, [snap?.self_healing_items]);

  const narrative = useMemo(() => {
    if (!snap) return "";
    const f = snap.narrative_facts;
    const agg = f.aggregateLevel;
    let aggLine = t("pages.selfHealing.narrative.aggregateUnknown");
    if (agg === "green") aggLine = t("pages.selfHealing.narrative.aggregateGreen");
    else if (agg === "degraded")
      aggLine = t("pages.selfHealing.narrative.aggregateDegraded");
    else if (agg === "red") aggLine = t("pages.selfHealing.narrative.aggregateRed");

    const counts = t("pages.selfHealing.narrative.counts", {
      ok: f.healthyCount,
      degraded: f.degradedCount,
      down: f.downCount,
      nc: f.notConfiguredCount,
      inc: f.openIncidentCount,
    });

    const edge = f.edgeBlocksReads
      ? t("pages.selfHealing.narrative.edgeBlocks")
      : t("pages.selfHealing.narrative.edgeOk");

    const worst = f.worstComponentIds.length
      ? t("pages.selfHealing.narrative.worst", {
          list: f.worstComponentIds
            .map((id) => t(`pages.selfHealing.components.${id}.name`))
            .join(", "),
        })
      : t("pages.selfHealing.narrative.noWorst");

    return [aggLine, counts, edge, worst, t("pages.selfHealing.narrative.footer")].join(
      "\n\n",
    );
  }, [snap, t]);

  const incidentBlock = (inc: SelfHealingIncident) => (
    <article
      key={inc.id}
      className="self-healing-incident"
      data-severity={inc.severity}
    >
      <header className="self-healing-incident__head">
        <span className={severityClass(inc.severity)}>{inc.severity}</span>
        <span className="muted small">{t(inc.areaLabelKey)}</span>
      </header>
      <h4 className="self-healing-incident__title">{inc.headline}</h4>
      <dl className="self-healing-dl">
        <dt>{t("pages.selfHealing.fields.lastSeen")}</dt>
        <dd>{new Date(inc.lastSeenMs).toISOString()}</dd>
        {inc.startedAtMs ? (
          <>
            <dt>{t("pages.selfHealing.fields.started")}</dt>
            <dd>{new Date(inc.startedAtMs).toISOString()}</dd>
          </>
        ) : null}
        <dt>{t("pages.selfHealing.fields.cause")}</dt>
        <dd>{inc.suspectedCause}</dd>
        <dt>{t("pages.selfHealing.fields.impact")}</dt>
        <dd>{inc.impact}</dd>
        <dt>{t("pages.selfHealing.fields.auto")}</dt>
        <dd>
          <ul className="self-healing-list">
            {inc.autoRemediations.map((x) => (
              <li key={x.slice(0, 80)}>{x}</li>
            ))}
          </ul>
        </dd>
        <dt>{t("pages.selfHealing.fields.next")}</dt>
        <dd>{inc.nextStep}</dd>
      </dl>
      <details className="self-healing-details">
        <summary>{t("pages.selfHealing.fields.technical")}</summary>
        <pre className="self-healing-pre">{inc.technicalDetail}</pre>
      </details>
      <div className="self-healing-actions">
        <button
          type="button"
          className="public-btn ghost"
          disabled={repairing}
          onClick={() => void runRepair("full_stack_refresh", inc.componentId ?? undefined)}
        >
          {t("pages.selfHealing.buttons.serverRecheck")}
        </button>
      </div>
    </article>
  );

  return (
    <div className="self-healing-hub">
      <div className="self-healing-toolbar panel">
        <div className="self-healing-toolbar__lead">
          <p className="muted small" style={{ margin: 0 }}>
            {t("pages.selfHealing.toolbarLead")}
          </p>
          {snap?.support_reference ? (
            <p className="muted small" style={{ margin: "6px 0 0" }}>
              {t("pages.selfHealing.supportRef", {
                ref: snap.support_reference,
              })}
            </p>
          ) : null}
        </div>
        <div className="self-healing-toolbar__actions">
          <button
            type="button"
            className="public-btn"
            disabled={loading || repairing}
            onClick={() => void load("manual")}
          >
            {loading ? t("pages.selfHealing.buttons.loading") : t("pages.selfHealing.buttons.refresh")}
          </button>
          <button
            type="button"
            className="public-btn ghost"
            disabled={repairing}
            onClick={() => void runRepair("full_stack_refresh")}
          >
            {t("pages.selfHealing.buttons.fullRecheck")}
          </button>
          <Link
            href={consolePath("health")}
            className="public-btn ghost"
            scroll={false}
          >
            {t("pages.selfHealing.buttons.openHealth")}
          </Link>
          <Link
            href={consolePath("diagnostics")}
            className="public-btn ghost"
            scroll={false}
          >
            {t("pages.selfHealing.buttons.openDiagnostics")}
          </Link>
          <a
            className="public-btn ghost"
            href="/api/dashboard/edge-status"
            target="_blank"
            rel="noreferrer"
          >
            {t("pages.selfHealing.buttons.edgeJson")}
          </a>
        </div>
      </div>

      {err ? (
        <div className="panel self-healing-error" role="alert">
          {err}
        </div>
      ) : null}

      {repairing ? (
        <p className="muted small self-healing-banner" role="status">
          {t("pages.selfHealing.repairing")}
        </p>
      ) : null}

      <section className="panel self-healing-section" aria-labelledby="sh-narrative">
        <h2 id="sh-narrative">{t("pages.selfHealing.sectionNarrative")}</h2>
        <p className="self-healing-narrative">{narrative || "…"}</p>
        <p className="muted small">{t("pages.selfHealing.narrativeDisclaimer")}</p>
      </section>

      {snap && snapshotWarrantsSituationExplain(snap) ? (
        <div className="panel self-healing-section">
          <SituationAiExplainPanel variant="snapshot" snapshot={snap} />
        </div>
      ) : null}

      <section className="panel self-healing-section" aria-labelledby="sh-healing">
        <h2 id="sh-healing">{t("pages.selfHealing.sectionHealing")}</h2>
        <ul className="self-healing-hint-list">
          {(snap?.healing_hints ?? []).map((h) => (
            <li key={h.id}>{t(h.messageKey)}</li>
          ))}
        </ul>
      </section>

      <section className="panel self-healing-section" aria-labelledby="sh-auto-recover">
        <h2 id="sh-auto-recover">
          {t("pages.selfHealing.sectionAutoRecover")}
        </h2>
        <p className="muted small">
          {t("pages.selfHealing.sectionAutoRecoverLead")}
        </p>
        {snap?.self_healing_error ? (
          <p className="small self-healing-sev--warning" role="status">
            {snap.self_healing_error}
          </p>
        ) : null}
        <div className="self-healing-repair-row" style={{ marginBottom: "0.75rem" }}>
          {["feature-engine", "drawing-engine", "signal-engine"].map((id) => (
            <button
              key={id}
              type="button"
              className="public-btn ghost self-healing-mini-btn"
              onClick={() => {
                void runRepair("worker_restart", undefined, id);
              }}
            >
              {t("pages.selfHealing.buttons.restartWorker", { name: id })}
            </button>
          ))}
        </div>
        <p className="muted small">
          {t("pages.selfHealing.autoRecoverDegradedOnly")}
        </p>
        {recoveryTimeline.length ? (
          <ol
            className="self-healing-history"
            style={{ marginTop: "0.5rem" }}
            aria-label={t("pages.selfHealing.recoveryTimelineAria")}
          >
            {recoveryTimeline.slice(0, 20).map((e, i) => (
              <li key={`${e.ts_ms}-${e.line}-${i}`}>
                <time dateTime={new Date(e.ts_ms).toISOString()}>
                  {new Date(e.ts_ms).toLocaleString()}
                </time>
                {" — "}
                <span className="small">{e.line}</span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted small">
            {t("pages.selfHealing.noRecoveryTimelineYet")}
          </p>
        )}
      </section>

      <section className="panel self-healing-section" aria-labelledby="sh-manual">
        <h2 id="sh-manual">{t("pages.selfHealing.sectionManual")}</h2>
        <p className="muted small">{t("pages.selfHealing.sectionManualLead")}</p>
        <div className="self-healing-incident-stack">
          {(snap?.not_auto_fixable ?? []).map(incidentBlock)}
          {!snap?.not_auto_fixable.length && !loading ? (
            <p className="muted small">{t("pages.selfHealing.noneManual")}</p>
          ) : null}
        </div>
      </section>

      <section className="panel self-healing-section" aria-labelledby="sh-incidents">
        <h2 id="sh-incidents">{t("pages.selfHealing.sectionIncidents")}</h2>
        <p className="muted small">{t("pages.selfHealing.sectionIncidentsLead")}</p>
        <div className="self-healing-incident-stack">
          {(snap?.incidents ?? []).map(incidentBlock)}
        </div>
      </section>

      <section className="panel self-healing-section" aria-labelledby="sh-components">
        <h2 id="sh-components">{t("pages.selfHealing.sectionComponents")}</h2>
        <p className="muted small">{t("pages.selfHealing.sectionComponentsLead")}</p>
        <div className="self-healing-table-wrap">
          <table className="self-healing-table">
            <thead>
              <tr>
                <th>{t("pages.selfHealing.thComponent")}</th>
                <th>{t("pages.selfHealing.thCategory")}</th>
                <th>{t("pages.selfHealing.thStatus")}</th>
                <th>{t("pages.selfHealing.thCause")}</th>
                <th>{t("pages.selfHealing.thRepairs")}</th>
              </tr>
            </thead>
            <tbody>
              {(snap?.components ?? []).map((c) => (
                <tr key={c.id}>
                  <td>{t(`pages.selfHealing.components.${c.id}.name`)}</td>
                  <td className="muted small">{t(c.categoryKey)}</td>
                  <td>
                    <span className={statusClass(c.status)}>{c.status}</span>
                  </td>
                  <td className="small">{c.suspectedCause.slice(0, 200)}</td>
                  <td>
                    <div className="self-healing-repair-row">
                      {c.availableRepairs.map((a) => (
                        <button
                          key={a.id}
                          type="button"
                          className="public-btn ghost self-healing-mini-btn"
                          onClick={() => {
                            if (
                              a.kind === "refetch_health" ||
                              a.kind === "recheck_connection"
                            ) {
                              void runRepair("full_stack_refresh", c.id);
                            } else {
                              repairHandler(a, router);
                            }
                          }}
                        >
                          {t(a.labelKey)}
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel self-healing-section" aria-labelledby="sh-history">
        <h2 id="sh-history">{t("pages.selfHealing.sectionHistory")}</h2>
        <p className="muted small">{t("pages.selfHealing.sectionHistoryLead")}</p>
        <ol className="self-healing-history">
          {history.map((h, i) => (
            <li key={`${h.ts_ms}-${i}`}>
              <time dateTime={new Date(h.ts_ms).toISOString()}>
                {new Date(h.ts_ms).toLocaleString()}
              </time>
              {" — "}
              <span>{h.summary}</span>
              {h.detail ? (
                <>
                  {" "}
                  <span className="muted small">({h.detail})</span>
                </>
              ) : null}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
