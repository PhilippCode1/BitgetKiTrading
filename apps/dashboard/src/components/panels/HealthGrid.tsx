import { formatTsMs } from "@/lib/format";
import type { ExecutionTierSnapshot, SystemHealthResponse } from "@/lib/types";

type Translate = (
  key: string,
  vars?: Record<string, string | number>,
) => string;

type Props = Readonly<{
  health: SystemHealthResponse;
  /** Kurzer Kontext unter der Ausführungsüberschrift (lokalisiert). */
  executionExplainer?: string | null;
  t: Translate;
}>;

const gk = (k: string) => `pages.health.grid.${k}` as const;

export function HealthGrid({ health, executionExplainer, t }: Props) {
  const { data_freshness, execution, ops, server_ts_ms } = health;
  const ds = health.database_schema;
  const rt = execution.execution_runtime as
    | {
        execution_tier?: ExecutionTierSnapshot;
        executionTier?: ExecutionTierSnapshot;
      }
    | undefined;
  const tier = rt?.execution_tier ?? rt?.executionTier;
  return (
    <>
      <div className="panel">
        <h2>{t(gk("executionTitle"))}</h2>
        {executionExplainer ? (
          <p className="muted small">{executionExplainer}</p>
        ) : null}
        <ul className="news-list">
          <li>
            {t(gk("executionMode"))}:{" "}
            <strong>{execution.execution_mode}</strong>
          </li>
          <li>
            {t(gk("strategyMode"))}:{" "}
            <strong>{execution.strategy_execution_mode}</strong>
          </li>
          <li>
            {t(gk("paperPath"))}:{" "}
            <strong>{String(execution.paper_path_active)}</strong>
          </li>
          <li>
            {t(gk("shadowGate"))}:{" "}
            <strong>{String(execution.shadow_trade_enable)}</strong>
          </li>
          <li>
            {t(gk("shadowPath"))}:{" "}
            <strong>{String(execution.shadow_path_active)}</strong>
          </li>
          <li>
            {t(gk("liveGate"))}:{" "}
            <strong>{String(execution.live_trade_enable)}</strong>
          </li>
          <li>
            {t(gk("liveSubmission"))}:{" "}
            <strong>{String(execution.live_order_submission_enabled)}</strong>
          </li>
          {tier ? (
            <>
              <li>
                {t(gk("tradingPlane"))}: <strong>{tier.trading_plane}</strong>
              </li>
              <li>
                {t(gk("deployment"))}: <strong>{tier.deployment}</strong> (
                {t(gk("deploymentAppEnv"))} {tier.app_env})
              </li>
              <li>
                {t(gk("bitgetDemo"))}:{" "}
                <strong>{String(tier.bitget_demo_enabled)}</strong>
              </li>
              <li>
                {t(gk("automatedLiveOrders"))}:{" "}
                <strong>{String(tier.automated_live_orders_enabled)}</strong>
              </li>
            </>
          ) : null}
        </ul>
      </div>
      <div className="panel">
        <h2>{t(gk("freshnessTitle"), { symbol: health.symbol })}</h2>
        <ul className="news-list">
          <li>
            {t(gk("lastCandle"))}:{" "}
            <strong>
              {formatTsMs(data_freshness.last_candle_ts_ms ?? undefined)}
            </strong>
          </li>
          <li>
            {t(gk("lastSignal"))}:{" "}
            <strong>
              {formatTsMs(data_freshness.last_signal_ts_ms ?? undefined)}
            </strong>
          </li>
          <li>
            {t(gk("lastNews"))}:{" "}
            <strong>
              {formatTsMs(data_freshness.last_news_ts_ms ?? undefined)}
            </strong>
          </li>
          <li className="muted">
            {t(gk("serverTime"))}: {formatTsMs(server_ts_ms)}
          </li>
        </ul>
      </div>
      <div className="panel">
        <h2>{t(gk("opsTitle"))}</h2>
        <ul className="news-list">
          <li>
            {t(gk("database"))}: <strong>{health.database}</strong>
            {health.database === "ok" ? (
              <span className="muted">{t(gk("databaseOkHint"))}</span>
            ) : (
              <span className="muted">{t(gk("databaseBadHint"))}</span>
            )}
          </li>
          {ds ? (
            <>
              <li>
                {t(gk("schemaStatus"))}: <strong>{ds.status ?? "—"}</strong>
                {ds.migration_catalog_available === false ? (
                  <span className="muted">
                    {" "}
                    {t(gk("migrationCatalogNote"))}
                  </span>
                ) : null}
              </li>
              {typeof ds.expected_migration_files === "number" &&
              typeof ds.applied_migration_files === "number" ? (
                <li>
                  {t(gk("migrationsFiles"))}{" "}
                  <strong>{ds.applied_migration_files}</strong> /{" "}
                  {t(gk("migrationsExpected"))}{" "}
                  <strong>{ds.expected_migration_files}</strong>
                </li>
              ) : null}
              {ds.pending_migrations_preview &&
              ds.pending_migrations_preview.length > 0 ? (
                <li className="muted">
                  {t(gk("pendingPreview"))}:{" "}
                  {ds.pending_migrations_preview.join(", ")}
                  {(ds.pending_migrations?.length ?? 0) >
                  ds.pending_migrations_preview.length
                    ? " …"
                    : ""}
                </li>
              ) : null}
              {ds.missing_tables && ds.missing_tables.length > 0 ? (
                <li className="muted">
                  {t(gk("missingTables"))}:{" "}
                  {ds.missing_tables.slice(0, 8).join(", ")}
                </li>
              ) : null}
              {ds.connect_error ? (
                <li className="muted">
                  {t(gk("connectError"))}: {ds.connect_error}
                </li>
              ) : null}
            </>
          ) : null}
          <li>
            {t(gk("monitorOpenAlerts"))}:{" "}
            <strong>{ops.monitor.open_alert_count}</strong>
          </li>
          <li>
            {t(gk("alertOutboxPending"))}:{" "}
            <strong>{ops.alert_engine.outbox_pending}</strong>
          </li>
          <li>
            {t(gk("alertOutboxFailed"))}:{" "}
            <strong>{ops.alert_engine.outbox_failed}</strong>
          </li>
          <li>
            {t(gk("liveReconcile"))}:{" "}
            <strong>{ops.live_broker.latest_reconcile_status ?? "—"}</strong>
          </li>
          <li>
            {t(gk("liveReconcileTime"))}:{" "}
            <strong>
              {ops.live_broker.latest_reconcile_created_ts ?? "—"}
            </strong>
          </li>
          <li>
            {t(gk("activeKillSwitches"))}:{" "}
            <strong>{ops.live_broker.active_kill_switch_count}</strong>
          </li>
          <li>
            {t(gk("lastFill"))}:{" "}
            <strong>{ops.live_broker.last_fill_created_ts ?? "—"}</strong>
          </li>
          <li>
            {t(gk("criticalAudits24h"))}:{" "}
            <strong>{ops.live_broker.critical_audit_count_24h}</strong>
          </li>
        </ul>
      </div>
      <div className="panel">
        <h2>{t(gk("servicesTitle"))}</h2>
        <div className="health-grid">
          {health.services.map((s) => {
            const name = s.name;
            const st = s.status;
            const ok = st === "ok";
            return (
              <div key={name} className={`health-card ${ok ? "ok" : "err"}`}>
                <strong>{name}</strong>
                <div>
                  {t(gk("statusLabel"))}: {st}
                </div>
                {s.ready === false && s.failed_checks?.length ? (
                  <div className="muted">
                    {t(gk("checksFailed"))}: {s.failed_checks.join(", ")}
                  </div>
                ) : null}
                {typeof s.execution_mode === "string" ? (
                  <div>
                    {t(gk("modeLabel"))}: {s.execution_mode}
                  </div>
                ) : null}
                {typeof s.strategy_execution_mode === "string" ? (
                  <div>
                    {t(gk("strategyLabel"))}: {s.strategy_execution_mode}
                  </div>
                ) : null}
                {typeof s.latency_ms === "number" ? (
                  <div>{s.latency_ms} ms</div>
                ) : null}
                {typeof s.open_alert_count === "number" ? (
                  <div>
                    {t(gk("openAlerts"))}: {s.open_alert_count}
                  </div>
                ) : null}
                {typeof s.outbox_pending === "number" ? (
                  <div>
                    {t(gk("outboxPending"))}: {s.outbox_pending}
                  </div>
                ) : null}
                {typeof s.outbox_failed === "number" ? (
                  <div>
                    {t(gk("outboxFailed"))}: {s.outbox_failed}
                  </div>
                ) : null}
                {typeof s.last_run_ts_ms === "number" ? (
                  <div>
                    {t(gk("lastRun"))}: {formatTsMs(s.last_run_ts_ms)}
                  </div>
                ) : null}
                {s.last_error ? (
                  <div className="muted">
                    {t(gk("errorLabel"))}: {s.last_error}
                  </div>
                ) : null}
                {s.detail ? (
                  <div className="muted">
                    {t(gk("apiHttp"))}: {s.detail}
                  </div>
                ) : null}
                {s.note ? <div className="muted">{s.note}</div> : null}
              </div>
            );
          })}
        </div>
      </div>
      <div className="panel">
        <h2>{t(gk("redisStreamsTitle"))}</h2>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t(gk("thStream"))}</th>
                <th>{t(gk("thLength"))}</th>
              </tr>
            </thead>
            <tbody>
              {health.stream_lengths_top.map((r) => (
                <tr key={r.name}>
                  <td>{r.name}</td>
                  <td>{r.length ?? r.error ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted">
          {t(gk("redisPing"))}: {health.redis ?? "—"}
        </p>
      </div>
    </>
  );
}
