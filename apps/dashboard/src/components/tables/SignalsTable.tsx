"use client";

import Link from "next/link";

import type { TranslateFn } from "@/components/i18n/I18nProvider";
import { DataTableSkeleton } from "@/components/ui/DataTableSkeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { useI18n } from "@/components/i18n/I18nProvider";
import { consolePath } from "@/lib/console-paths";
import {
  formatDistancePctField,
  formatNum,
  formatPct01,
  formatTsMs,
} from "@/lib/format";
import type { SignalRecentItem } from "@/lib/types";

type Props = Readonly<{
  items: SignalRecentItem[];
  isLoading?: boolean;
}>;

function dirClass(d: string): string {
  if (d === "long") return "dir-long";
  if (d === "short") return "dir-short";
  return "dir-neutral";
}

function shortCanon(id: string | null | undefined): string {
  if (!id) return "—";
  const parts = id.split(":");
  return parts.length >= 4
    ? `${parts[2] ?? ""}:${parts[3] ?? id}`.slice(0, 22)
    : id.slice(0, 22);
}

function instrumentContext(s: SignalRecentItem): string {
  const parts = [
    s.market_family,
    s.instrument_product_type,
    s.instrument_margin_account_mode,
  ].filter((value): value is string => Boolean(value && value.trim()));
  return parts.length ? parts.join(" / ") : "—";
}

function metadataLine(s: SignalRecentItem, t: TranslateFn): string {
  const flags: string[] = [];
  if (s.instrument_metadata_verified === true)
    flags.push(t("signalsTable.metaVerified"));
  if (s.instrument_metadata_verified === false)
    flags.push(t("signalsTable.metaUnverified"));
  if (s.instrument_supports_leverage === true)
    flags.push(t("signalsTable.metaLev"));
  if (s.instrument_supports_reduce_only === true)
    flags.push(t("signalsTable.metaReduceOnly"));
  if (s.instrument_supports_long_short === true)
    flags.push(t("signalsTable.metaLongShort"));
  return flags.join(" · ") || t("signalsTable.noMetaFlags");
}

function govLiveLabel(
  s: SignalRecentItem,
  t: TranslateFn,
): { text: string; cls: string } {
  const blocks = Array.isArray(s.live_execution_block_reasons_json)
    ? s.live_execution_block_reasons_json.length
    : 0;
  if (s.live_execution_clear_for_real_money === true && blocks === 0) {
    return { text: t("signalsTable.liveFree"), cls: "status-pill status-ok" };
  }
  if (blocks > 0) {
    return {
      text: t("signalsTable.liveBlocked", { count: blocks }),
      cls: "status-pill status-warn",
    };
  }
  return { text: "—", cls: "status-pill" };
}

function executionLabel(
  s: SignalRecentItem,
  t: TranslateFn,
): { text: string; cls: string } {
  if (s.operator_release_exists) {
    return { text: t("signalsTable.released"), cls: "status-pill status-ok" };
  }
  if (s.latest_execution_decision_action === "live_candidate_recorded") {
    return {
      text: t("signalsTable.approvalPending"),
      cls: "status-pill status-warn",
    };
  }
  if (s.latest_execution_decision_action === "blocked") {
    return { text: t("signalsTable.blocked"), cls: "status-pill status-warn" };
  }
  if (s.latest_execution_decision_action) {
    return { text: s.latest_execution_decision_action, cls: "status-pill" };
  }
  return { text: "—", cls: "status-pill" };
}

function telegramRow(
  s: SignalRecentItem,
  t: TranslateFn,
): { text: string; cls: string } {
  const state = (s.telegram_delivery_state ?? "").toLowerCase();
  if (state === "sent")
    return {
      text: t("signalsTable.telegramSent"),
      cls: "status-pill status-ok",
    };
  if (state === "failed")
    return {
      text: t("signalsTable.telegramFailed"),
      cls: "status-pill status-warn",
    };
  if (state === "pending") {
    return {
      text: t("signalsTable.telegramStatePending"),
      cls: "status-pill status-warn",
    };
  }
  if (state === "sending") {
    return {
      text: t("signalsTable.telegramStateSending"),
      cls: "status-pill status-warn",
    };
  }
  return { text: "—", cls: "status-pill" };
}

function opGateYesNo(v: boolean | null | undefined, t: TranslateFn): string {
  if (v === true) return t("signalsTable.opGateYes");
  if (v === false) return t("signalsTable.opGateNo");
  return "—";
}

function cashYesNo(v: boolean | null | undefined, t: TranslateFn): string {
  return opGateYesNo(v, t);
}

export function SignalsTable({ items, isLoading = false }: Props) {
  const { t } = useI18n();

  if (isLoading) {
    return (
      <DataTableSkeleton
        columnCount={12}
        rowCount={8}
        ariaLabelKey="signalsTable.skeletonAria"
        listClassName="signals-mobile-cards"
        tableWrapClassName="signals-table-wide"
      />
    );
  }

  if (items.length === 0) {
    return (
      <EmptyState
        icon="layers"
        className="empty-state-help"
        titleKey="help.signals.emptyTitle"
        descriptionKey="help.signals.emptyBody"
        stepKeys={[
          "help.signals.step1",
          "help.signals.step2",
          "help.signals.step3",
        ]}
        cta={{ labelKey: "ui.emptyState.resetFilters", href: consolePath("signals") }}
        commsPhase="partial"
        showActions
      />
    );
  }
  return (
    <>
      <ul
        className="console-stack-list signals-mobile-cards console-mobile-only"
        aria-label={t("pages.signals.title")}
      >
        {items.map((s) => {
          const g = govLiveLabel(s, t);
          const e = executionLabel(s, t);
          return (
            <li key={`m-${s.signal_id}`} className="console-stack-card">
              <div className="console-stack-card__meta">
                <span className="mono-small">
                  {formatTsMs(s.analysis_ts_ms)}
                </span>
                <span className="muted small">{s.timeframe}</span>
                <span className={`status-pill ${dirClass(s.direction)}`}>
                  {s.direction}
                </span>
              </div>
              <p className="console-stack-card__title">{s.symbol}</p>
              <p className="muted small">{instrumentContext(s)}</p>
              <div className="console-stack-card__dl">
                <div>
                  <span className="console-stack-card__k">
                    {t("signalsTable.thDecision")}
                  </span>
                  <span className="console-stack-card__v mono-small">
                    {s.trade_action ?? "—"}
                  </span>
                </div>
                <div>
                  <span className="console-stack-card__k">
                    {t("signalsTable.thRiskGov")}
                  </span>
                  <span className={`console-stack-card__v ${g.cls}`}>
                    {g.text}
                  </span>
                </div>
                <div>
                  <span className="console-stack-card__k">
                    {t("signalsTable.thExecution")}
                  </span>
                  <span className={`console-stack-card__v ${e.cls}`}>
                    {e.text}
                  </span>
                </div>
              </div>
              <div className="signals-mobile-card__actions">
                <Link
                  href={consolePath(`signals/${s.signal_id}`)}
                  className="public-btn ghost"
                >
                  {t("signalsTable.detail")}
                </Link>
              </div>
            </li>
          );
        })}
      </ul>
      <div className="table-wrap signals-table-wide console-desktop-only">
        <table className="data-table data-table--dense">
          <thead>
            <tr>
              <th title={t("signalsTable.thTime")}>
                {t("signalsTable.thTime")}
              </th>
              <th
                title={`${t("signalsTable.thInstrument")} — ${t("glossary.console.canonicalInstrument")}`}
              >
                {t("signalsTable.thInstrument")}
              </th>
              <th title={t("glossary.console.timeframe")}>
                {t("signalsTable.thTf")}
              </th>
              <th>{t("signalsTable.thDir")}</th>
              <th title={t("glossary.console.thDecision")}>
                {t("signalsTable.thDecision")}
              </th>
              <th title={t("glossary.console.thSpecialists")}>
                {t("signalsTable.thSpecialists")}
              </th>
              <th title={t("glossary.console.thStopLev")}>
                {t("signalsTable.thStopLev")}
              </th>
              <th title={t("glossary.console.thRiskGov")}>
                {t("signalsTable.thRiskGov")}
              </th>
              <th title={t("glossary.console.thExecution")}>
                {t("signalsTable.thExecution")}
              </th>
              <th title={t("signalsTable.telegramTitle")}>
                {t("signalsTable.thTelegram")}
              </th>
              <th title={t("glossary.console.thOutcome")}>
                {t("signalsTable.thOutcome")}
              </th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((s) => {
              const g = govLiveLabel(s, t);
              const e = executionLabel(s, t);
              const tg = telegramRow(s, t);
              const uniN = Array.isArray(
                s.governor_universal_hard_block_reasons_json,
              )
                ? s.governor_universal_hard_block_reasons_json.length
                : 0;
              return (
                <tr key={s.signal_id}>
                  <td>{formatTsMs(s.analysis_ts_ms)}</td>
                  <td>
                    <div className="stacked-cell">
                      <strong>{s.symbol}</strong>
                      <span className="stacked-muted">
                        {instrumentContext(s)}
                      </span>
                      <span
                        className="mono-small"
                        title={s.canonical_instrument_id ?? ""}
                      >
                        {shortCanon(s.canonical_instrument_id)}
                      </span>
                      <span className="stacked-muted">
                        {metadataLine(s, t)}
                      </span>
                    </div>
                  </td>
                  <td>{s.timeframe}</td>
                  <td className={dirClass(s.direction)}>{s.direction}</td>
                  <td>
                    <div className="stacked-cell">
                      <span className="mono-small">
                        {s.trade_action ?? "—"}
                      </span>
                      <span
                        className="stacked-muted"
                        title={t("signalsTable.metaDecisionTitle")}
                      >
                        {t("signalsTable.metaLabel")}:{" "}
                        {s.meta_decision_action ?? "—"}
                      </span>
                      <span className="stacked-muted">
                        {t("signalsTable.laneLabel")}:{" "}
                        {s.meta_trade_lane ?? "—"}
                      </span>
                      <span className="stacked-muted">
                        {t("signalsTable.regimeLabel")}:{" "}
                        {s.regime_state ?? s.market_regime ?? "—"}
                      </span>
                      <span className="stacked-muted">
                        {t("signalsTable.strength")}{" "}
                        {formatNum(s.signal_strength_0_100, 1)} /{" "}
                        {t("signalsTable.policy")}{" "}
                        {formatPct01(s.decision_confidence_0_1 ?? null)}
                      </span>
                    </div>
                  </td>
                  <td>
                    <div className="stacked-cell">
                      <span className="mono-small" title={s.playbook_id ?? ""}>
                        {s.playbook_id ?? "—"}
                      </span>
                      <span className="stacked-muted">
                        {t("signalsTable.family")}: {s.playbook_family ?? "—"} /{" "}
                        {t("signalsTable.exit")}:{" "}
                        {s.exit_family_effective_primary ?? "—"}
                      </span>
                      <span
                        className="mono-small"
                        title={s.specialist_router_id ?? ""}
                      >
                        {t("signalsTable.router")}:{" "}
                        {(s.specialist_router_id ?? "—").slice(0, 32)}
                      </span>
                      <span className="stacked-muted">
                        {t("signalsTable.opGate")}:{" "}
                        {opGateYesNo(s.router_operator_gate_required, t)}
                      </span>
                    </div>
                  </td>
                  <td>
                    <div className="stacked-cell">
                      <span className="mono-small">
                        {formatDistancePctField(s.stop_distance_pct ?? null)} /{" "}
                        {formatDistancePctField(
                          s.stop_budget_max_pct_allowed ?? null,
                        )}
                      </span>
                      <span className="stacked-muted">
                        {t("signalsTable.minExec")}{" "}
                        {formatDistancePctField(
                          s.stop_min_executable_pct ?? null,
                        )}
                      </span>
                      <span className="stacked-muted">
                        {t("signalsTable.fragil")}{" "}
                        {s.stop_fragility_0_1 != null
                          ? formatNum(s.stop_fragility_0_1, 2)
                          : "—"}{" "}
                        / {t("signalsTable.exec")}{" "}
                        {s.stop_executability_0_1 != null
                          ? formatNum(s.stop_executability_0_1, 2)
                          : "—"}
                      </span>
                      <span className="stacked-muted">
                        {t("signalsTable.lev")}{" "}
                        {s.recommended_leverage == null
                          ? "—"
                          : `${s.recommended_leverage}x`}{" "}
                        / {t("signalsTable.levFree")}{" "}
                        {s.allowed_leverage == null
                          ? "—"
                          : `${s.allowed_leverage}x`}
                      </span>
                    </div>
                  </td>
                  <td>
                    <div className="stacked-cell">
                      <span className={g.cls}>{g.text}</span>
                      <span className="stacked-muted">
                        {t("signalsTable.universal")} {uniN} /{" "}
                        {t("signalsTable.cash")}{" "}
                        {cashYesNo(s.live_execution_clear_for_real_money, t)}
                      </span>
                      <span
                        className="stacked-muted"
                        title={t("glossary.console.bps")}
                      >
                        {t("signalsTable.probLabel")}{" "}
                        {formatPct01(s.probability_0_1)} /{" "}
                        {t("signalsTable.takeTradeLabel")}{" "}
                        {formatPct01(s.take_trade_prob ?? null)}
                      </span>
                      <span
                        className="stacked-muted"
                        title={t("glossary.console.expectedReturnBps")}
                      >
                        {t("signalsTable.edgeBpsLabel")}{" "}
                        {s.expected_return_bps == null
                          ? "—"
                          : `${formatNum(s.expected_return_bps, 1)} ${t("signalsTable.bpsSuffix")}`}
                      </span>
                    </div>
                  </td>
                  <td>
                    <div className="stacked-cell">
                      <span className={e.cls}>{e.text}</span>
                      <span className="stacked-muted">
                        {s.latest_execution_runtime_mode ?? "—"} /{" "}
                        {s.latest_execution_decision_reason ?? "—"}
                      </span>
                      <span className="stacked-muted">
                        {t("signalsTable.mirror")}{" "}
                        {s.live_mirror_eligible == null
                          ? "—"
                          : String(s.live_mirror_eligible)}{" "}
                        / {t("signalsTable.shadowLiveApprox")}{" "}
                        {s.shadow_live_match_ok == null
                          ? "—"
                          : String(s.shadow_live_match_ok)}
                      </span>
                      <span className="mono-small">
                        {s.latest_execution_id
                          ? s.latest_execution_id.slice(0, 12)
                          : "—"}
                      </span>
                    </div>
                  </td>
                  <td>
                    <div className="stacked-cell">
                      <span className={tg.cls}>{tg.text}</span>
                      <span className="stacked-muted">
                        {s.telegram_alert_type ?? "—"} / {t("signalsTable.msg")}{" "}
                        {s.telegram_message_id ?? "—"}
                      </span>
                      <span className="stacked-muted">
                        {s.telegram_sent_ts ?? t("signalsTable.noDelivery")}
                      </span>
                    </div>
                  </td>
                  <td>
                    <div className="stacked-cell">
                      {s.outcome_badge ? (
                        <span className="status-pill">
                          {t("signalsTable.outcomeWL", {
                            wins: s.outcome_badge.wins,
                            losses: s.outcome_badge.losses,
                            rate: formatPct01(s.outcome_badge.win_rate),
                          })}
                        </span>
                      ) : (
                        <span className="stacked-muted">
                          {t("signalsTable.noOutcomeYet")}
                        </span>
                      )}
                      <span className="stacked-muted">{s.decision_state}</span>
                    </div>
                  </td>
                  <td>
                    <Link href={consolePath(`signals/${s.signal_id}`)}>
                      {t("signalsTable.detail")}
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
