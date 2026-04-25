import { CONSOLE_BASE } from "@/lib/console-paths";

const SAFE_PREFIXES = ["/console", "/onboarding", "/welcome"] as const;
const OPS_LEGACY_PREFIX = "/ops";

function looksExternal(target: string): boolean {
  return /^(?:https?:)?\/\//i.test(target);
}

function normalizeOpsLegacy(pathname: string): string {
  if (pathname === OPS_LEGACY_PREFIX) {
    return `${CONSOLE_BASE}/ops`;
  }
  if (pathname.startsWith(`${OPS_LEGACY_PREFIX}/`)) {
    return `${CONSOLE_BASE}${pathname}`;
  }
  return pathname;
}

export function sanitizeReturnTo(
  rawReturnTo: string | null | undefined,
  fallback: string = CONSOLE_BASE,
): string {
  const raw = (rawReturnTo ?? "").trim();
  if (!raw) {
    return fallback;
  }

  let candidate = raw;
  if (!candidate.startsWith("/") && candidate.includes("%")) {
    try {
      candidate = decodeURIComponent(candidate);
    } catch {
      return fallback;
    }
  }

  if (!candidate.startsWith("/") || looksExternal(candidate)) {
    return fallback;
  }

  let parsed: URL;
  try {
    parsed = new URL(candidate, "http://localhost");
  } catch {
    return fallback;
  }

  if (parsed.origin !== "http://localhost") {
    return fallback;
  }

  const safePathname = normalizeOpsLegacy(parsed.pathname);
  if (safePathname === "/") {
    return fallback;
  }

  if (!SAFE_PREFIXES.some((prefix) => safePathname.startsWith(prefix))) {
    return fallback;
  }

  return `${safePathname}${parsed.search}`;
}
