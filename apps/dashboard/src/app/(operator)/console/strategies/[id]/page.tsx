import Link from "next/link";

import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { ConsoleSurfaceNotice } from "@/components/console/ConsoleSurfaceNotice";
import { Header } from "@/components/layout/Header";
import { StrategyStatusActions } from "@/components/panels/StrategyStatusActions";
import { fetchStrategyDetail } from "@/lib/api";
import { consolePath } from "@/lib/console-paths";
import { formatTsMs } from "@/lib/format";
import {
  diagnosticFromSearchParams,
  type ConsoleSearchParams,
} from "@/lib/console-params";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { resolveStrategyMutationsVisible } from "@/lib/operator-session";

export const dynamic = "force-dynamic";

type P = { id: string };

export default async function StrategyDetailPage(props: {
  params: P | Promise<P>;
  searchParams?: ConsoleSearchParams | Promise<ConsoleSearchParams>;
}) {
  const sp = await Promise.resolve(props.searchParams ?? {});
  const diagnostic = diagnosticFromSearchParams(sp);
  const t = await getServerTranslator();
  const { id } = await Promise.resolve(props.params);
  const allowMutations = await resolveStrategyMutationsVisible();
  let row: import("@/lib/types").StrategyDetailResponse | null = null;
  let err: string | null = null;
  try {
    row = await fetchStrategyDetail(id);
  } catch (e) {
    err = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  if (err || !row) {
    return (
      <>
        <Header title={t("console.nav.strategies")} />
        <div className="panel" role="status">
          {err ? (
            <PanelDataIssue err={err} diagnostic={diagnostic} t={t} />
          ) : (
            <ConsoleSurfaceNotice
              t={t}
              titleKey="pages.strategiesDetail.notFoundTitle"
              bodyKey="pages.strategiesDetail.notFound"
              refreshKey="ui.surfaceState.notFound.refreshHint"
              showStateActions
              wrapActions
            />
          )}
          <Link
            href={consolePath("strategies")}
            className="public-btn ghost"
            style={{ marginTop: 12, display: "inline-block" }}
          >
            ← {t("pages.strategiesDetail.backToList")}
          </Link>
        </div>
      </>
    );
  }

  const lifecycle =
    row.lifecycle_status ??
    (row.current_status ? row.current_status : "not_set");
  const perf = row.performance_rolling ?? [];
  const sigPath = row.signal_path ?? {
    matching_signal_count: 0,
    last_signal_ts_ms: null,
    match_rule_de: "",
  };
  const aiBlock = row.ai_explanations ?? {
    availability: "none",
    hint_de: "",
  };

  return (
    <>
      <Header title={row.name} subtitle={row.strategy_id} />
      <p>
        <Link href={consolePath("strategies")}>
          ← {t("pages.strategiesDetail.backToList")}
        </Link>
      </p>
      <div className="panel">
        <h2>{t("pages.strategiesDetail.statusTitle")}</h2>
        <p>
          {t("pages.strategiesDetail.lifecycleLabel")}:{" "}
          <span className="status-pill">
            {lifecycle === "not_set"
              ? t("pages.strategiesList.statusNotSet")
              : lifecycle}
          </span>
        </p>
        <p className="muted small">
          {t("pages.strategiesDetail.currentLabel")}:{" "}
          {row.current_status ?? "—"}
        </p>
        <p className="muted">
          {t("pages.strategiesDetail.updatedLabel")}:{" "}
          {row.status_updated_ts ?? "—"}
        </p>
        <h3 className="small" style={{ marginTop: "1rem" }}>
          {t("pages.strategiesDetail.metadataTitle")}
        </h3>
        <div className="signal-grid">
          <div>
            <span className="label">
              {t("pages.strategiesDetail.scopeCanonicalInstrument")}
            </span>
            <div className="mono-small">
              {row.scope_json.canonical_instrument_id ?? "—"}
            </div>
          </div>
          <div>
            <span className="label">
              {t("pages.strategiesDetail.scopeCategory")}
            </span>
            <div>
              {row.scope_json.market_family ?? "—"}
              {row.scope_json.product_type
                ? ` / ${row.scope_json.product_type}`
                : ""}
            </div>
          </div>
          <div>
            <span className="label">
              {t("pages.strategiesDetail.scopeSymbol")}
            </span>
            <div>{row.scope_json.symbol ?? "—"}</div>
          </div>
          <div>
            <span className="label">
              {t("pages.strategiesDetail.scopeMarginMode")}
            </span>
            <div>{row.scope_json.margin_account_mode ?? "—"}</div>
          </div>
          <div>
            <span className="label">
              {t("pages.strategiesDetail.scopeMetadata")}
            </span>
            <div className="mono-small">
              {t("pages.strategiesDetail.scopeMetadataLine", {
                source: row.scope_json.metadata_source ?? "—",
                verified: String(row.scope_json.metadata_verified ?? false),
              })}
            </div>
          </div>
          <div>
            <span className="label">
              {t("pages.strategiesDetail.scopeEligibility")}
            </span>
            <div>
              {t("pages.strategiesDetail.scopeEligibilityLine", {
                inv: row.scope_json.inventory_visible
                  ? t("pages.signalsDetail.boolYes")
                  : t("pages.signalsDetail.boolNo"),
                analytics: row.scope_json.analytics_eligible
                  ? t("pages.signalsDetail.boolYes")
                  : t("pages.signalsDetail.boolNo"),
                paper: row.scope_json.paper_shadow_eligible
                  ? t("pages.signalsDetail.boolYes")
                  : t("pages.signalsDetail.boolNo"),
                live: row.scope_json.live_execution_enabled
                  ? t("pages.signalsDetail.boolYes")
                  : t("pages.signalsDetail.boolNo"),
              })}
            </div>
          </div>
          <div>
            <span className="label">
              {t("pages.strategiesDetail.scopeCapabilities")}
            </span>
            <div>
              {t("pages.strategiesDetail.scopeCapabilitiesLine", {
                lev: row.scope_json.supports_leverage
                  ? t("pages.signalsDetail.boolYes")
                  : t("pages.signalsDetail.boolNo"),
                short: row.scope_json.supports_shorting
                  ? t("pages.signalsDetail.boolYes")
                  : t("pages.signalsDetail.boolNo"),
                reduce: row.scope_json.supports_reduce_only
                  ? t("pages.signalsDetail.boolYes")
                  : t("pages.signalsDetail.boolNo"),
              })}
            </div>
          </div>
          <div>
            <span className="label">
              {t("pages.strategiesDetail.scopeTimeframes")}
            </span>
            <div>
              {Array.isArray(row.scope_json.timeframes)
                ? row.scope_json.timeframes.join(", ") || "—"
                : "—"}
            </div>
          </div>
        </div>
        <details style={{ marginTop: 12 }}>
          <summary className="operator-details-summary">
            {t("pages.strategiesDetail.scopeRawJsonToggle")}
          </summary>
          <pre className="json-mini">
            {JSON.stringify(row.scope_json, null, 2)}
          </pre>
        </details>
      </div>

      <div className="panel">
        <h2>{t("pages.strategiesDetail.performanceTitle")}</h2>
        {perf.length === 0 ? (
          <div role="status">
            <p className="muted">
              {t("pages.strategiesDetail.performanceEmpty")}
            </p>
            {row.performance_rolling_empty_hint_de ? (
              <p className="muted small" style={{ marginTop: 8 }}>
                {row.performance_rolling_empty_hint_de}
              </p>
            ) : null}
          </div>
        ) : (
          <ul className="news-list">
            {perf.map((p, i) => (
              <li key={`${p.time_window ?? i}`}>
                <strong>
                  {t("pages.strategiesDetail.performanceWindow")}:
                </strong>{" "}
                {p.time_window ?? "—"} —{" "}
                {t("pages.strategiesDetail.updatedLabel")}:{" "}
                {p.updated_ts ?? "—"}
                <pre className="json-mini" style={{ marginTop: 8 }}>
                  {JSON.stringify(p.metrics_json ?? {}, null, 2)}
                </pre>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="panel">
        <h2>{t("pages.strategiesDetail.signalPathTitle")}</h2>
        <p>
          {t("pages.strategiesDetail.signalPathCount")}:{" "}
          <strong>{sigPath.matching_signal_count}</strong>
        </p>
        <p>
          {t("pages.strategiesDetail.signalPathLast")}:{" "}
          {formatTsMs(sigPath.last_signal_ts_ms)}
        </p>
        <p className="muted small">
          {t("pages.strategiesDetail.signalPathRule")}
        </p>
        <p className="muted small">{sigPath.match_rule_de}</p>
        {sigPath.signals_link_hint_de ? (
          <p className="muted small">{sigPath.signals_link_hint_de}</p>
        ) : null}
        <p>
          <Link
            href={`${consolePath("signals")}?signal_registry_key=${encodeURIComponent(sigPath.registry_key ?? row.name)}`}
          >
            {t("pages.strategiesDetail.signalPathOpen")}
          </Link>
        </p>
      </div>

      <div className="panel">
        <h2>{t("pages.strategiesDetail.aiTitle")}</h2>
        <p className="muted small">{t("pages.strategiesDetail.aiLead")}</p>
        <p className="muted small" role="status">
          {aiBlock.hint_de}
        </p>
      </div>

      <StrategyStatusActions
        strategyId={row.strategy_id}
        allowMutations={allowMutations}
      />
      <div className="panel">
        <h2>{t("pages.strategiesDetail.versionsTitle")}</h2>
        {row.versions.length === 0 ? (
          <p className="muted" role="status">
            {t("pages.strategiesDetail.versionsEmpty")}
          </p>
        ) : (
          <ul className="news-list">
            {row.versions.map((v) => (
              <li key={v.strategy_version_id}>
                {v.version} — {v.created_ts}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="panel">
        <h2>{t("pages.strategiesDetail.statusHistoryTitle")}</h2>
        {row.status_history.length === 0 ? (
          <p className="muted" role="status">
            {t("pages.strategiesDetail.statusHistoryEmpty")}
          </p>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("pages.strategiesDetail.statusHistoryThTime")}</th>
                  <th>{t("pages.strategiesDetail.statusHistoryThFrom")}</th>
                  <th>{t("pages.strategiesDetail.statusHistoryThTo")}</th>
                  <th>{t("pages.strategiesDetail.statusHistoryThReason")}</th>
                </tr>
              </thead>
              <tbody>
                {row.status_history.map((h, i) => (
                  <tr key={i}>
                    <td>{h.ts}</td>
                    <td>{h.old_status}</td>
                    <td>{h.new_status}</td>
                    <td>{h.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
