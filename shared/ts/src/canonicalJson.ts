/**
 * Muss byte-kompatibel zu shared_py.eventbus.canonical sein (pytest + Jest Golden).
 */

const FLOAT_DECIMALS = 8;

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

export function canonicalizeJsonValue(value: unknown): unknown {
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
  if (Array.isArray(value)) {
    return value.map((v) => canonicalizeJsonValue(v));
  }
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const keys = Object.keys(obj).sort();
    const out: Record<string, unknown> = {};
    for (const k of keys) {
      out[k] = canonicalizeJsonValue(obj[k]);
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
