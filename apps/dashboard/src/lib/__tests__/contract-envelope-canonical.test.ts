import { createHash } from "crypto";
import { readFileSync } from "fs";
import path from "path";

import {
  ENVELOPE_FINGERPRINT_CANON_VERSION,
  envelopeFingerprintPreimage,
  stableJsonStringify,
} from "@bitget-btc-ai/shared-ts";

function sha256Hex(s: string): string {
  return createHash("sha256").update(s, "utf8").digest("hex");
}

const REPO_FIXTURES = path.join(
  __dirname,
  "../../../../../tests/fixtures/contracts",
);

function readGolden(name: string): string {
  return readFileSync(path.join(REPO_FIXTURES, name), "utf8")
    .trim()
    .split(/\s+/)[0]!;
}

describe("Event envelope canonical fingerprint (Python parity)", () => {
  const fixturePath = path.join(REPO_FIXTURES, "envelope_candle_close_ok.json");

  it("matches golden semantic SHA-256", () => {
    const raw = JSON.parse(readFileSync(fixturePath, "utf8")) as Record<
      string,
      unknown
    >;
    const preimage = envelopeFingerprintPreimage(
      raw,
      "semantic",
      ENVELOPE_FINGERPRINT_CANON_VERSION,
    );
    const body = stableJsonStringify(preimage);
    expect(sha256Hex(body)).toBe(
      readGolden("envelope_candle_close_ok.semantic.sha256"),
    );
  });

  it("matches golden wire SHA-256", () => {
    const raw = JSON.parse(readFileSync(fixturePath, "utf8")) as Record<
      string,
      unknown
    >;
    const preimage = envelopeFingerprintPreimage(
      raw,
      "wire",
      ENVELOPE_FINGERPRINT_CANON_VERSION,
    );
    const body = stableJsonStringify(preimage);
    expect(sha256Hex(body)).toBe(
      readGolden("envelope_candle_close_ok.wire.sha256"),
    );
  });

  it("is invariant to shuffled payload key order", () => {
    const raw = JSON.parse(readFileSync(fixturePath, "utf8")) as Record<
      string,
      unknown
    >;
    const p = raw.payload as Record<string, unknown>;
    const keys = Object.keys(p).sort().reverse();
    const shuffled: Record<string, unknown> = {};
    for (const k of keys) {
      shuffled[k] = p[k];
    }
    const a = envelopeFingerprintPreimage(
      raw,
      "semantic",
      ENVELOPE_FINGERPRINT_CANON_VERSION,
    );
    const b = envelopeFingerprintPreimage(
      { ...raw, payload: shuffled },
      "semantic",
      ENVELOPE_FINGERPRINT_CANON_VERSION,
    );
    expect(stableJsonStringify(a)).toBe(stableJsonStringify(b));
  });
});
