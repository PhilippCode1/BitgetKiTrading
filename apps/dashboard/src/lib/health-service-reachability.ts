import type {
  SystemHealthResponse,
  SystemHealthServiceItem,
} from "@/lib/types";

export type ServiceReachabilityStats = Readonly<{
  total: number;
  notOk: number;
  timeoutLike: number;
  connectionRefusedLike: number;
}>;

function probeText(s: SystemHealthServiceItem): string {
  return `${s.detail ?? ""} ${s.last_error ?? ""}`.toLowerCase();
}

function isTimeoutLike(s: SystemHealthServiceItem): boolean {
  if (s.status === "ok") return false;
  const t = probeText(s);
  return t.includes("timeout") || t.includes("timed out");
}

function isConnectionRefusedLike(s: SystemHealthServiceItem): boolean {
  if (s.status === "ok") return false;
  const t = probeText(s);
  return (
    t.includes("connection refused") ||
    t.includes("errno 111") ||
    t.includes("actively refused")
  );
}

/**
 * Zaehlt Dienst-Probleme; viele Timeouts = typisch falsche HEALTH_URL / Compose nicht erreichbar.
 */
export function analyzeServiceReachability(
  health: SystemHealthResponse,
): ServiceReachabilityStats {
  const services = health.services ?? [];
  let notOk = 0;
  let timeoutLike = 0;
  let connectionRefusedLike = 0;
  for (const s of services) {
    if (s.status === "ok") continue;
    notOk++;
    if (isTimeoutLike(s)) timeoutLike++;
    if (isConnectionRefusedLike(s)) connectionRefusedLike++;
  }
  return { total: services.length, notOk, timeoutLike, connectionRefusedLike };
}

/**
 * True wenn die Health-Ansicht sehr wahrscheinlich **Erreichbarkeit** zeigt, nicht „fachliche“ Degradation.
 */
export function showConnectivityFirstAid(
  health: SystemHealthResponse,
): boolean {
  const a = analyzeServiceReachability(health);
  if (a.total === 0) return false;
  if (a.timeoutLike >= 4) return true;
  if (a.notOk >= 6 && a.timeoutLike >= 2) return true;
  if (a.connectionRefusedLike >= 2 && a.notOk >= 3) return true;
  return false;
}

export type ConnectivitySupplements = Readonly<{
  /** monitor-engine: nichts hoert auf Zielport (Dienst down / falscher HEALTH_URL). */
  monitorEngineConnectionRefused: boolean;
  /** z. B. news + llm ok, Rest ~2s Timeout — HEALTH_URL_* inkonsistent. */
  partialReachabilityPattern: boolean;
}>;

/**
 * Zusaetzliche, situationsspezifische Hinweise unter dem Erreichbarkeits-Banner.
 */
export function connectivitySupplements(
  health: SystemHealthResponse,
): ConnectivitySupplements {
  const services = health.services ?? [];
  let ok = 0;
  let monitorEngineConnectionRefused = false;
  for (const s of services) {
    if (s.status === "ok") ok++;
    if (s.name === "monitor-engine" && isConnectionRefusedLike(s)) {
      monitorEngineConnectionRefused = true;
    }
  }
  const a = analyzeServiceReachability(health);
  const partialReachabilityPattern =
    ok >= 2 && a.notOk >= 5 && a.timeoutLike >= 3;
  return { monitorEngineConnectionRefused, partialReachabilityPattern };
}

/**
 * Admin-Hub: Kachel „System health“ grün, wenn der Kernpfad laut Gateway ohne Warnungen ist.
 *
 * GET /v1/system/health liefert **kein** Top-Level-`status` und kein `overall.ok`;
 * stattdessen u. a. `database` (z. B. `"ok"`) und `warnings` (Codes).
 *
 * @see services/api-gateway/src/api_gateway/routes_system_health.py — `compute_system_health_payload`
 */
export function systemHealthAdminHubGreen(
  health: SystemHealthResponse | null,
): boolean {
  if (!health) return false;
  if (health.database !== "ok") return false;
  const w = health.warnings;
  if (!Array.isArray(w) || w.length > 0) return false;
  return true;
}
