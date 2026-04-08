import {
  classifyFetchErrorMessage,
  type FetchErrorKind,
} from "@/lib/user-facing-fetch-error";

/** Cockpit-Module, die parallel per Gateway geladen werden — fuer Kaskaden-Deduplizierung. */
export type OpsModuleId =
  | "health"
  | "liveState"
  | "models"
  | "liveBrokerRuntime"
  | "killSwitch"
  | "orders"
  | "fills"
  | "paperPositions"
  | "paperMetrics"
  | "monitorAlerts"
  | "onlineDrift"
  | "learningDrift"
  | "liveDecisions"
  | "alertOutbox"
  | "paperTrades";

const TRANSPORT_KINDS: ReadonlySet<FetchErrorKind> = new Set([
  "unreachable",
  "timeout",
  "bad_gateway",
  "bff_unreachable",
  "server_error",
  "unauthorized",
  "forbidden",
]);

/** Ab zwei Modulen: auch „weiche“ Transportarten (Timeout, 5xx) als Kaskade. */
const CASCADE_MIN_MODULES = 2;

/**
 * Diese Arten schon ab einem Modul als zentralen Incident werten (klarer Single-Point-of-Failure).
 */
const SINGLE_MODULE_CASCADE_KINDS: ReadonlySet<FetchErrorKind> = new Set([
  "unreachable",
  "bff_unreachable",
  "bad_gateway",
  "unauthorized",
  "forbidden",
]);

function cascadeMinModules(kind: FetchErrorKind): number {
  return SINGLE_MODULE_CASCADE_KINDS.has(kind) ? 1 : CASCADE_MIN_MODULES;
}

export type TransportIncidentSeverity = "blocker" | "degraded";

export function severityForTransportKind(
  kind: FetchErrorKind,
): TransportIncidentSeverity {
  if (kind === "unauthorized" || kind === "forbidden") return "blocker";
  return "degraded";
}

/** Normalisiert API-Pfade, damit „GET /v1/foo“ und „GET /v1/bar“ zur selben Ursache gruppieren. */
export function fingerprintFetchErrorMessage(raw: string): string {
  let s = raw
    .replace(/GET\s+\/v1\/[^\s?]+(?:\?[^\s]*)?/gi, "GET /v1/…")
    .replace(/https?:\/\/[^\s)'"]+/gi, "http://…")
    .replace(/HTTP\s+\d{3}/gi, "HTTP …")
    .replace(/\(\d+(?:\.\d+)?ms\)/gi, "(…)")
    .replace(/\s+/g, " ")
    .trim();

  const looksLikeSharedConnectivity =
    /API_GATEWAY|DASHBOARD_GATEWAY|gateway|bff|\/api\/dashboard\/gateway|503|502|504|ECONNREFUSED|ETIMEDOUT|ENOTFOUND|fetch failed|failed to fetch|nicht erreichbar|unterbrochen|network error|dashboard-bff/i.test(
      raw,
    );
  if (looksLikeSharedConnectivity && /GET\s+\/v1\/…/i.test(s)) {
    return "GET /v1/… (shared connectivity)";
  }
  return s.slice(0, 200);
}

export type TransportCascade = Readonly<{
  kind: FetchErrorKind;
  severity: TransportIncidentSeverity;
  affectedModules: OpsModuleId[];
  sampleRaw: string;
  count: number;
}>;

export type SecondaryIncidentGroup = Readonly<{
  kind: FetchErrorKind;
  modules: OpsModuleId[];
  sampleRaw: string;
}>;

export type AggregatedOpsFetchState = Readonly<{
  /** Gemeinsame Transport-/Gateway-Stoerung mit vielen betroffenen Modulen */
  transportCascade: TransportCascade | null;
  /** Module, die nur kompakt „siehe oben“ zeigen sollen */
  suppressedModules: ReadonlySet<OpsModuleId>;
  /** Abweichende oder kleine Fehlergruppen (eigene Ursache) */
  secondaryIncidents: SecondaryIncidentGroup[];
  /** Rohe Fehleranzahl (ohne Deduplizierung) */
  totalFailedModules: number;
}>;

type Bucket = {
  fp: string;
  kind: FetchErrorKind;
  modules: OpsModuleId[];
  sample: string;
};

/**
 * Fasst parallele Fetch-Fehler zusammen: eine Gateway-Kaskade erzeugt einen Incident statt N roter Bloecke.
 */
export function aggregateOpsFetchFailures(
  modules: ReadonlyArray<{ id: OpsModuleId; error: string | null }>,
): AggregatedOpsFetchState {
  const withErr = modules.filter((m): m is { id: OpsModuleId; error: string } =>
    Boolean(m.error),
  );
  if (withErr.length === 0) {
    return {
      transportCascade: null,
      suppressedModules: new Set(),
      secondaryIncidents: [],
      totalFailedModules: 0,
    };
  }

  const buckets = new Map<string, Bucket>();
  for (const { id, error } of withErr) {
    const kind = classifyFetchErrorMessage(error);
    const fp = fingerprintFetchErrorMessage(error);
    const key = `${kind}::${fp}`;
    const existing = buckets.get(key);
    if (existing) {
      existing.modules.push(id);
    } else {
      buckets.set(key, { fp, kind, modules: [id], sample: error });
    }
  }

  let transportCascade: TransportCascade | null = null;
  for (const b of buckets.values()) {
    if (!TRANSPORT_KINDS.has(b.kind)) continue;
    if (b.modules.length < cascadeMinModules(b.kind)) continue;
    if (
      !transportCascade ||
      b.modules.length > transportCascade.affectedModules.length
    ) {
      transportCascade = {
        kind: b.kind,
        severity: severityForTransportKind(b.kind),
        affectedModules: [...b.modules],
        sampleRaw: b.sample,
        count: b.modules.length,
      };
    }
  }

  const suppressedModules = new Set<OpsModuleId>();
  if (transportCascade) {
    for (const id of transportCascade.affectedModules)
      suppressedModules.add(id);
  }

  const secondaryIncidents: SecondaryIncidentGroup[] = [];
  for (const b of buckets.values()) {
    const remaining = b.modules.filter((m) => !suppressedModules.has(m));
    if (remaining.length === 0) continue;
    secondaryIncidents.push({
      kind: b.kind,
      modules: remaining,
      sampleRaw: b.sample,
    });
  }

  return {
    transportCascade,
    suppressedModules,
    secondaryIncidents,
    totalFailedModules: withErr.length,
  };
}

export function isOpsModuleSuppressed(
  id: OpsModuleId,
  suppressed: ReadonlySet<OpsModuleId>,
): boolean {
  return suppressed.has(id);
}
