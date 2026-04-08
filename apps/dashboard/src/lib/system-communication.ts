import type { LiveDataSurfaceModel } from "@/lib/live-data-surface-model";

/**
 * Einheitliche System-Kommunikation: Zustände, die Nutzer:innen Orientierung geben,
 * ohne zu überfrachten. Siehe `systemComms.*` in messages (de/en).
 */
export type SystemCommsPhase =
  | "loading"
  | "connected"
  | "partial"
  | "unstable"
  | "blocked"
  | "self_healing"
  | "action_required"
  | "unknown";

export type LiveDataExpectation = Readonly<{
  phase: SystemCommsPhase;
  /** i18n-Schlüssel für den Erwartungs-/Kontextabsatz unter der Live-Datenlage */
  expectationKey: string;
  /** Optionale Vars für expectationKey */
  expectationVars?: Record<string, string | number>;
}>;

/**
 * Leitet einen Kommunikationsphasen-Typ aus dem Live-Daten-Oberflächenmodell ab.
 * Lane (Paper/Shadow/Live) bleibt separat in der UI; hier geht es um Verbindungs-/Datenrealität.
 */
export function liveDataSurfaceToCommsPhase(
  model: LiveDataSurfaceModel,
): SystemCommsPhase {
  if (model.loading || model.primaryBadge === "LOADING") return "loading";
  if (model.fetchFailed || model.primaryBadge === "ERROR") return "blocked";
  if (model.primaryBadge === "NO_LIVE" || model.primaryBadge === "STALE") {
    return "unstable";
  }
  if (
    model.primaryBadge === "PARTIAL" ||
    model.primaryBadge === "DEGRADED_READ"
  ) {
    return "partial";
  }
  if (model.primaryBadge === "LIVE") {
    if (model.executionLane === "paper" || model.executionLane === "shadow") {
      return "partial";
    }
    return "connected";
  }
  return "unknown";
}

/**
 * Kurzer Erwartungstext: was der Nutzer als Nächstes erwarten darf / worauf achten.
 */
export function liveDataSurfaceToExpectation(
  model: LiveDataSurfaceModel,
): LiveDataExpectation {
  const phase = liveDataSurfaceToCommsPhase(model);
  const badge = model.primaryBadge;

  if (model.loading || badge === "LOADING") {
    return { phase, expectationKey: "systemComms.expectation.loading" };
  }
  if (model.fetchFailed || badge === "ERROR") {
    return { phase, expectationKey: "systemComms.expectation.fetchFailed" };
  }
  if (badge === "NO_LIVE") {
    return { phase, expectationKey: "systemComms.expectation.noLive" };
  }
  if (badge === "STALE") {
    return { phase, expectationKey: "systemComms.expectation.stale" };
  }
  if (badge === "DEGRADED_READ") {
    return { phase, expectationKey: "systemComms.expectation.degradedRead" };
  }
  if (badge === "PARTIAL") {
    if (model.surfaceKind === "signals_list") {
      return {
        phase,
        expectationKey: "systemComms.expectation.partialSignals",
      };
    }
    return { phase, expectationKey: "systemComms.expectation.partialGeneric" };
  }
  if (badge === "LIVE") {
    if (model.demoOrFixture) {
      return { phase, expectationKey: "systemComms.expectation.liveDemo" };
    }
    if (model.executionLane === "paper") {
      return {
        phase: "partial",
        expectationKey: "systemComms.expectation.execLanePaper",
      };
    }
    if (model.executionLane === "shadow") {
      return {
        phase: "partial",
        expectationKey: "systemComms.expectation.execLaneShadow",
      };
    }
    if (model.lineageTotal > 0 && model.lineageWithData < model.lineageTotal) {
      return {
        phase: "partial",
        expectationKey: "systemComms.expectation.liveLineageGaps",
        expectationVars: {
          ok: model.lineageWithData,
          total: model.lineageTotal,
        },
      };
    }
    return { phase, expectationKey: "systemComms.expectation.liveOk" };
  }
  return { phase, expectationKey: "systemComms.expectation.unknown" };
}
