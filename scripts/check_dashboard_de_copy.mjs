#!/usr/bin/env node
/**
 * Prüft apps/dashboard/src/messages/de.json auf rohe API-/Persistenz-Namen (snake_case)
 * in ausgewählten Nutzerflächen.
 *
 * Standard: nur „strikte“ Präfixe (einfache Ansicht, Live-Seitenleiste, Health-Grid).
 * Vollständiger Scan: STRICT_LOCALE_CHECK=all node scripts/check_dashboard_de_copy.mjs
 *
 * diagnostic.* ist immer ausgenommen (Support-Texte).
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DE_PATH = join(__dirname, "../apps/dashboard/src/messages/de.json");

const SNAKE_RE = /\b[a-z][a-z0-9]*_[a-z0-9_]+\b/g;

const EXTRA_TERM_RE =
  /\b(reasons_json|signal_explanations|explain_short|trade_action|market_family|canonical_instrument_id)\b/gi;

/** Standard: diese Pfade sollen freundliche Copy ohne Feldnamen-Jargon bleiben */
const STRICT_PREFIXES = [
  "simple.",
  "welcome.",
  "live.signalPanel.",
  "live.paperPanel.",
  "live.newsPanel.",
  "live.lineage.",
  "pages.health.grid.",
];

function shouldSkipKeyPath(path, fullScan) {
  if (path.startsWith("diagnostic.")) return true;
  if (fullScan) {
    if (path.includes(".demoReason.")) return true;
    if (
      path.endsWith(".hintOpsMarketFamily") ||
      path.endsWith(".hintOpsCanonicalId") ||
      path.endsWith(".hintOpsSignalFamily")
    ) {
      return true;
    }
    return false;
  }
  if (
    !STRICT_PREFIXES.some((pre) => path === pre || path.startsWith(`${pre}`))
  ) {
    return true;
  }
  return false;
}

function flatten(prefix, obj, out) {
  if (typeof obj === "string") {
    out.push([prefix, obj]);
    return;
  }
  if (obj === null || typeof obj !== "object") return;
  for (const [k, v] of Object.entries(obj)) {
    const p = prefix ? `${prefix}.${k}` : k;
    flatten(p, v, out);
  }
}

function main() {
  const fullScan = process.env.STRICT_LOCALE_CHECK === "all";
  const raw = readFileSync(DE_PATH, "utf8");
  const data = JSON.parse(raw);
  const pairs = [];
  flatten("", data, pairs);

  const hits = [];
  for (const [path, value] of pairs) {
    if (typeof value !== "string" || shouldSkipKeyPath(path, fullScan))
      continue;
    const snakes = value.match(SNAKE_RE);
    const extras = value.match(EXTRA_TERM_RE);
    if (snakes?.length) {
      hits.push({ path, kind: "snake_case", matches: [...new Set(snakes)] });
    }
    if (extras?.length) {
      hits.push({
        path,
        kind: "internal_token",
        matches: [...new Set(extras.map((x) => x.toLowerCase()))],
      });
    }
  }

  if (hits.length === 0) {
    console.log(
      `check_dashboard_de_copy: OK (${fullScan ? "Vollscan" : "strikt: simple/welcome/live.*Panel|lineage/pages.health.grid"}).`,
    );
    return;
  }

  console.error(
    "check_dashboard_de_copy: Verdächtige deutsche Nutzerstrings:\n",
  );
  for (const h of hits) {
    console.error(`  [${h.kind}] ${h.path}`);
    console.error(`    → ${h.matches.join(", ")}`);
  }
  console.error(
    "\nTipp: Mit STRICT_LOCALE_CHECK=all den gesamten Baum prüfen (viele erwartete Ops-Hinweise).",
  );
  process.exit(1);
}

main();
