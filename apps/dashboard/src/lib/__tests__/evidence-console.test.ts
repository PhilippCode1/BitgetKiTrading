import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";

import { buildEvidenceCards } from "@/lib/evidence-console";

function withTempDir(run: (dir: string) => void) {
  const dir = mkdtempSync(resolve(tmpdir(), "evidence-console-"));
  try {
    run(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function writeMatrix(root: string, content: string) {
  const p = resolve(root, "docs/production_10_10");
  mkdirSync(p, { recursive: true });
  writeFileSync(resolve(p, "evidence_matrix.yaml"), content, "utf-8");
}

describe("evidence-console", () => {
  it("fehlender Restore-Report blockiert Live", () => {
    withTempDir((root) => {
      writeMatrix(
        root,
        `
categories:
  - id: backup_restore
    status: verified
    next_action: Restore bleibt beobachtet.
`,
      );
      const cards = buildEvidenceCards({ rootDir: root, gitSha: "abc123" });
      const restore = cards.find((c) => c.id === "restore_test");
      expect(restore?.status).toBe("missing");
      expect(restore?.liveImpactDe).toMatch(/Live bleibt blockiert/i);
    });
  });

  it("fehlender Shadow-Burn-in blockiert Live", () => {
    withTempDir((root) => {
      writeMatrix(root, "categories: []");
      const cards = buildEvidenceCards({ rootDir: root });
      const shadow = cards.find((c) => c.id === "shadow_burn_in");
      expect(shadow?.blocksLive).toBe(true);
      expect(shadow?.statusLabelDe).toBe("fehlt");
    });
  });

  it("fehlender Bitget-Readiness-Nachweis blockiert Live", () => {
    withTempDir((root) => {
      writeMatrix(root, "categories: []");
      const cards = buildEvidenceCards({ rootDir: root });
      const bitget = cards.find((c) => c.id === "bitget_readiness");
      expect(bitget?.blocksLive).toBe(true);
      expect(bitget?.liveImpactDe).toContain("Nachweis fehlt");
    });
  });

  it("vorhandener Report wird als Pfad und Status angezeigt", () => {
    withTempDir((root) => {
      writeMatrix(
        root,
        `
categories:
  - id: market_data_quality_per_asset
    status: partial
    next_action: Data Quality weiter pruefen.
`,
      );
      mkdirSync(resolve(root, "reports"), { recursive: true });
      writeFileSync(
        resolve(root, "reports/market_data_quality_sample.md"),
        "# report",
        "utf-8",
      );
      const cards = buildEvidenceCards({ rootDir: root, gitSha: "0123456789abcdef" });
      const card = cards.find((c) => c.id === "asset_universe_quality");
      expect(card?.lastReportPath).toBe("reports/market_data_quality_sample.md");
      expect(card?.status).toBe("partial");
      expect(card?.gitSha).toBe("0123456789ab");
    });
  });

  it("kein Status wird faelschlich verified wenn Datei fehlt", () => {
    withTempDir((root) => {
      writeMatrix(
        root,
        `
categories:
  - id: shadow_burn_in
    status: verified
    next_action: ok
`,
      );
      const cards = buildEvidenceCards({ rootDir: root });
      const shadow = cards.find((c) => c.id === "shadow_burn_in");
      expect(shadow?.status).not.toBe("verified");
      expect(shadow?.status).toBe("missing");
    });
  });

  it("texte sind deutsch", () => {
    withTempDir((root) => {
      writeMatrix(root, "categories: []");
      const cards = buildEvidenceCards({ rootDir: root });
      expect(cards.every((c) => c.statusLabelDe.length > 0)).toBe(true);
      expect(cards.some((c) => /Live bleibt blockiert/.test(c.liveImpactDe))).toBe(
        true,
      );
    });
  });
});
