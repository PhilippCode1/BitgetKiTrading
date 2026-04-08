import fs from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

/**
 * Responsive Smoke + optionale Screenshots für docs/cursor_execution/47_responsive_assets/
 * (nur wenn Verzeichnis beschreibbar; bei `pnpm e2e` mit laufendem Dashboard).
 */
const ASSET_DIR = path.join(
  __dirname,
  "..",
  "..",
  "docs",
  "cursor_execution",
  "47_responsive_assets",
);

async function primeConsoleSession(page: import("@playwright/test").Page) {
  await page.goto("/console/account");
  await page.waitForLoadState("domcontentloaded");
}

function tryWriteScreenshot(name: string, buf: Buffer) {
  try {
    if (!fs.existsSync(ASSET_DIR)) {
      fs.mkdirSync(ASSET_DIR, { recursive: true });
    }
    fs.writeFileSync(path.join(ASSET_DIR, name), buf);
  } catch {
    /* lokales e2e ohne Schreibrecht: ignorieren */
  }
}

const CORE_PATHS = [
  "/console/health",
  "/console/paper",
  "/console/signals",
  "/console/terminal",
  "/console/live-broker",
  "/console/account",
  "/console/account/language",
] as const;

for (const viewport of [
  { tag: "mobile", width: 390, height: 844 },
  { tag: "tablet", width: 834, height: 1112 },
] as const) {
  test.describe(`Responsive shell (${viewport.tag})`, () => {
    test.beforeEach(async ({ page }) => {
      await page.setViewportSize({
        width: viewport.width,
        height: viewport.height,
      });
      await primeConsoleSession(page);
    });

    for (const p of CORE_PATHS) {
      test(`${p} lädt mit Sidebar und Hauptinhalt`, async ({ page }) => {
        const res = await page.goto(p, { waitUntil: "domcontentloaded" });
        expect(res?.ok(), `${p} HTTP ${res?.status()}`).toBeTruthy();
        await expect(page.locator(".dash-sidebar")).toBeVisible();
        await expect(page.locator("main.dash-main")).toBeVisible();
        if (p === "/console/terminal") {
          await expect(page.locator(".live-terminal-toolbar")).toBeVisible();
        } else {
          await expect(page.locator("main h1").first()).toBeVisible();
        }
      });
    }

    test(`Screenshot-Paket (${viewport.tag})`, async ({ page }) => {
      for (const p of CORE_PATHS) {
        await page.goto(p, { waitUntil: "domcontentloaded" });
        const buf = await page.screenshot({ fullPage: false });
        const safe = p.replace(/\//g, "_").replace(/^_/, "") || "root";
        tryWriteScreenshot(`${viewport.tag}-${safe}.png`, buf);
      }
    });
  });
}
