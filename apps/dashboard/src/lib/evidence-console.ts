import { existsSync, readFileSync, statSync } from "node:fs";
import { resolve } from "node:path";

const MATRIX_REL = "docs/production_10_10/evidence_matrix.yaml";

/** Gleiche Mindestregeln wie shared_py.owner_private_live_release_payload_ok (ohne Secrets). */
export function ownerPrivateLiveReleasePayloadOk(payload: unknown): boolean {
  if (payload === null || typeof payload !== "object") return false;
  const o = payload as Record<string, unknown>;
  if (o.owner_private_live_go !== true) return false;
  const ref = o.signoff_reference;
  if (typeof ref !== "string" || ref.trim().length < 8) return false;
  const rec = o.recorded_at;
  if (typeof rec !== "string" || rec.trim().length < 10) return false;
  return true;
}

/**
 * Monorepo-Wurzel finden (Dashboard laeuft unter apps/dashboard).
 * Optional: BITGET_BTC_AI_REPO_ROOT oder REPO_ROOT setzen.
 */
export function resolveDashboardRepoRoot(): string {
  for (const key of ["BITGET_BTC_AI_REPO_ROOT", "REPO_ROOT"] as const) {
    const v = process.env[key];
    if (v && existsSync(resolve(v, MATRIX_REL))) {
      return resolve(v);
    }
  }
  const twoUp = resolve(process.cwd(), "..", "..");
  if (existsSync(resolve(twoUp, MATRIX_REL))) {
    return twoUp;
  }
  const oneUp = resolve(process.cwd(), "..");
  if (existsSync(resolve(oneUp, MATRIX_REL))) {
    return oneUp;
  }
  return process.cwd();
}

const OWNER_RELEASE_REL = "reports/owner_private_live_release.json";

export type OwnerPrivateLiveReleaseGate = {
  fileRelative: string;
  filePresent: boolean;
  payloadValid: boolean;
  /** Entspricht Scorecard: ohne gueltige Datei kein private_live_allowed. */
  scorecardBlocksPrivateLive: boolean;
  summaryDe: string;
  templateRelative: string;
};

export function readOwnerPrivateLiveReleaseGate(rootDir: string): OwnerPrivateLiveReleaseGate {
  const abs = resolve(rootDir, OWNER_RELEASE_REL);
  const filePresent = existsSync(abs);
  let payloadValid = false;
  if (filePresent) {
    try {
      const raw = readFileSync(abs, "utf-8");
      payloadValid = ownerPrivateLiveReleasePayloadOk(JSON.parse(raw) as unknown);
    } catch {
      payloadValid = false;
    }
  }
  const scorecardBlocksPrivateLive = !payloadValid;
  let summaryDe: string;
  if (!filePresent) {
    summaryDe =
      "Lokale Datei fehlt — Scorecard setzt private_live_allowed auf NO_GO " +
      "(zusaetzlich zu Matrix/Evidence). Template: docs/production_10_10/owner_private_live_release.template.json";
  } else if (!payloadValid) {
    summaryDe =
      "Datei vorhanden, aber JSON ungueltig (owner_private_live_go, signoff_reference mind. 8 Zeichen, recorded_at). " +
      "private_live_allowed bleibt NO_GO.";
  } else {
    summaryDe =
      "Maschinelle Owner-Freigabe lokal gueltig. Live bleibt weiterhin durch Matrix und alle anderen Gates blockiert, bis verified.";
  }
  return {
    fileRelative: OWNER_RELEASE_REL,
    filePresent,
    payloadValid,
    scorecardBlocksPrivateLive,
    summaryDe,
    templateRelative: "docs/production_10_10/owner_private_live_release.template.json",
  };
}

export type EvidenceStatusCode =
  | "missing"
  | "partial"
  | "implemented"
  | "verified"
  | "external_required";

export type EvidenceCard = {
  id: string;
  title: string;
  status: EvidenceStatusCode;
  statusLabelDe: string;
  lastReportPath: string | null;
  lastReportDate: string | null;
  gitSha: string | null;
  liveImpactDe: string;
  nextStepDe: string;
  blocksLive: boolean;
};

type CardSpec = {
  id: string;
  title: string;
  categoryId: string;
  reportPath: string;
  defaultNextStep: string;
};

const CARD_SPECS: readonly CardSpec[] = [
  {
    id: "shadow_burn_in",
    title: "Shadow-Burn-in",
    categoryId: "shadow_burn_in",
    reportPath: "reports/shadow_burn_in_sample.md",
    defaultNextStep: "Shadow-Burn-in-Nachweis aktualisieren.",
  },
  {
    id: "bitget_readiness",
    title: "Bitget Readiness",
    categoryId: "bitget_exchange_readiness",
    reportPath: "reports/bitget_exchange_readiness_sample.md",
    defaultNextStep: "Bitget-Readiness-Check als Report ablegen.",
  },
  {
    id: "restore_test",
    title: "Restore-Test",
    categoryId: "backup_restore",
    reportPath: "reports/restore_test_sample.md",
    defaultNextStep: "Restore-Drill mit RTO/RPO dokumentieren.",
  },
  {
    id: "safety_drill",
    title: "Safety Drill",
    categoryId: "emergency_flatten",
    reportPath: "reports/live_safety_drill_sample.md",
    defaultNextStep: "Safety-Drill-Nachweis mit Ergebnis dokumentieren.",
  },
  {
    id: "alert_drill",
    title: "Alert Drill",
    categoryId: "alert_routing",
    reportPath: "reports/alert_routing_drill_sample.md",
    defaultNextStep: "Alert-Routing-Drill mit Zustellnachweis durchführen.",
  },
  {
    id: "performance_backtest",
    title: "Performance/Backtest/Walk-forward",
    categoryId: "strategy_validation_per_asset_class",
    reportPath: "reports/multi_asset_strategy_evidence_sample.md",
    defaultNextStep: "Strategie-Evidence pro Asset-Klasse nachziehen.",
  },
  {
    id: "asset_universe_quality",
    title: "Asset-Universum/Data Quality",
    categoryId: "market_data_quality_per_asset",
    reportPath: "reports/market_data_quality_sample.md",
    defaultNextStep: "Data-Quality-Nachweise pro Asset ergänzen.",
  },
  {
    id: "production_scorecard",
    title: "Production Scorecard",
    categoryId: "final_go_no_go_scorecard",
    reportPath: "reports/production_readiness_scorecard_sample.md",
    defaultNextStep: "Scorecard gegen aktuelle Evidence-Matrix prüfen.",
  },
  {
    id: "final_go_no_go",
    title: "Final Go/No-Go",
    categoryId: "final_go_no_go_scorecard",
    reportPath: "reports/production_readiness_scorecard_sample.md",
    defaultNextStep: "Owner-Go/No-Go erst nach vollständiger Evidence.",
  },
];

function statusLabelDe(status: EvidenceStatusCode): string {
  if (status === "missing") return "fehlt";
  if (status === "partial") return "teilweise";
  if (status === "implemented") return "implementiert";
  if (status === "verified") return "verifiziert";
  return "extern erforderlich";
}

function parseCategoryBlock(matrixRaw: string, categoryId: string): string | null {
  const marker = `- id: ${categoryId}`;
  const start = matrixRaw.indexOf(marker);
  if (start < 0) return null;
  const next = matrixRaw.indexOf("\n  - id:", start + marker.length);
  return next < 0 ? matrixRaw.slice(start) : matrixRaw.slice(start, next);
}

function parseCategoryStatus(
  matrixRaw: string,
  categoryId: string,
): { status: EvidenceStatusCode | null; nextAction: string | null } {
  const block = parseCategoryBlock(matrixRaw, categoryId);
  if (!block) return { status: null, nextAction: null };
  const statusMatch = block.match(/\n\s+status:\s+([a-z_]+)/);
  const nextMatch = block.match(/\n\s+next_action:\s+([^\n]+)/);
  const raw = statusMatch?.[1] ?? null;
  const status =
    raw === "missing" ||
    raw === "partial" ||
    raw === "implemented" ||
    raw === "verified" ||
    raw === "external_required"
      ? raw
      : null;
  return {
    status,
    nextAction: nextMatch?.[1]?.trim() ?? null,
  };
}

export function buildEvidenceCards(params?: {
  rootDir?: string;
  matrixPath?: string;
  gitSha?: string | null;
}): EvidenceCard[] {
  const rootDir = params?.rootDir ?? resolveDashboardRepoRoot();
  const matrixPath = params?.matrixPath ?? resolve(rootDir, MATRIX_REL);
  const gitSha =
    params?.gitSha ??
    process.env.VERCEL_GIT_COMMIT_SHA ??
    process.env.GIT_COMMIT_SHA ??
    null;
  const matrixRaw = existsSync(matrixPath)
    ? readFileSync(matrixPath, "utf-8")
    : "";

  return CARD_SPECS.map((spec) => {
    const reportAbs = resolve(rootDir, spec.reportPath);
    const reportExists = existsSync(reportAbs);
    const reportDate = reportExists ? statSync(reportAbs).mtime.toISOString() : null;
    const category = parseCategoryStatus(matrixRaw, spec.categoryId);
    let status: EvidenceStatusCode = category.status ?? "missing";
    if (!reportExists) status = "missing";
    if (reportExists && status === "missing") status = "implemented";
    const blocksLive = status !== "verified";
    const liveImpactDe = reportExists
      ? blocksLive
        ? "Nachweis vorhanden, aber nicht verifiziert. Live bleibt blockiert."
        : "Nachweis verifiziert. Kein Blocker aus dieser Karte."
      : "Nachweis fehlt, Live bleibt blockiert.";
    return {
      id: spec.id,
      title: spec.title,
      status,
      statusLabelDe: statusLabelDe(status),
      lastReportPath: reportExists ? spec.reportPath : null,
      lastReportDate: reportDate,
      gitSha: gitSha ? gitSha.slice(0, 12) : null,
      liveImpactDe,
      nextStepDe: category.nextAction ?? spec.defaultNextStep,
      blocksLive,
    };
  });
}
