/**
 * Muss byte-kompatibel zu shared_py.eventbus.canonical sein (pytest + Jest Golden).
 */

const FLOAT_DECIMALS = 8;

function isMsTimestampKey(k: string | undefined): boolean {
  if (k == null || k === "") {
    return false;
  }
  if (k === "exchange_ts_ms" || k === "ingest_ts_ms") {
    return true;
  }
  return k.endsWith("_ts_ms");
}

function msToIsoUtcZMicros(ms: number): string {
  if (!Number.isInteger(ms) || Object.is(ms, -0) || ms < 0) {
    throw new TypeError(String(ms));
  }
  const d = new Date(ms);
  if (d.getTime() !== ms) {
    throw new TypeError("Timestamp ausserhalb des darstellbaren Date-Bereichs");
  }
  const y = d.getUTCFullYear();
  const mo = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day = String(d.getUTCDate()).padStart(2, "0");
  const h = String(d.getUTCHours()).padStart(2, "0");
  const m = String(d.getUTCMinutes()).padStart(2, "0");
  const s = String(d.getUTCSeconds()).padStart(2, "0");
  const u = d.getUTCMilliseconds() * 1000;
  return `${y}-${mo}-${day}T${h}:${m}:${s}.${String(u).padStart(6, "0")}Z`;
}

function dateToIsoUtcZMicros(d: Date): string {
  if (Number.isNaN(d.getTime())) {
    throw new TypeError("Ungueltiges Date");
  }
  return msToIsoUtcZMicros(d.getTime());
}

function normalizeJsonNumber(n: number): number {
  if (!Number.isFinite(n)) {
    throw new Error("NaN/Inf in fingerprint material nicht erlaubt");
  }
  const rounded = Math.round(n * 10 ** FLOAT_DECIMALS) / 10 ** FLOAT_DECIMALS;
  const asInt = Math.trunc(rounded);
  const eps = 10 ** -(FLOAT_DECIMALS + 1);
  if (Math.abs(rounded - asInt) <= eps) {
    return asInt;
  }
  return rounded;
}

/**
 * @param key - JSON-Objektfeldname (fuer *_ts_ms → ISO) oder weglassen in Arrays.
 */
export function canonicalizeJsonValue(value: unknown, key?: string): unknown {
  if (key != null && isMsTimestampKey(key) && typeof value === "number" && Number.isInteger(value)) {
    return msToIsoUtcZMicros(value);
  }
  if (value === null || typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number") {
    if (Number.isInteger(value)) {
      return value;
    }
    return normalizeJsonNumber(value);
  }
  if (typeof value === "string") {
    return value;
  }
  if (value instanceof Date) {
    return dateToIsoUtcZMicros(value);
  }
  if (Array.isArray(value)) {
    return value.map((v) => canonicalizeJsonValue(v));
  }
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const keys = Object.keys(obj).sort();
    const out: Record<string, unknown> = {};
    for (const k of keys) {
      out[k] = canonicalizeJsonValue(obj[k], k);
    }
    return out;
  }
  throw new Error(`nicht unterstuetzter Typ: ${typeof value}`);
}

export function stableJsonStringify(obj: unknown): string {
  return JSON.stringify(canonicalizeJsonValue(obj));
}

export type FingerprintMode = "semantic" | "wire";

const SEMANTIC_FIELDS = [
  "schema_version",
  "event_type",
  "symbol",
  "instrument",
  "timeframe",
  "exchange_ts_ms",
  "dedupe_key",
  "payload",
  "trace",
] as const;

const WIRE_FIELDS = [
  "schema_version",
  "event_id",
  "event_type",
  "symbol",
  "instrument",
  "timeframe",
  "exchange_ts_ms",
  "ingest_ts_ms",
  "dedupe_key",
  "payload",
  "trace",
] as const;

function pickFields(
  data: Record<string, unknown>,
  fields: readonly string[],
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const k of fields) {
    if (Object.prototype.hasOwnProperty.call(data, k)) {
      out[k] = data[k];
    }
  }
  return out;
}

export function envelopeFingerprintPreimage(
  data: Record<string, unknown>,
  mode: FingerprintMode,
  canonVersion: string,
): Record<string, unknown> {
  const fields = mode === "semantic" ? SEMANTIC_FIELDS : WIRE_FIELDS;
  return {
    canon_version: canonVersion,
    fingerprint_mode: mode,
    envelope: pickFields(data, fields),
  };
}
