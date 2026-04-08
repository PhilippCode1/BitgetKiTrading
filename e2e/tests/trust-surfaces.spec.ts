import fs from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

/**
 * Smoke + Screenshots für Vertrauens- und Einstiegstexte (Lauf 49).
 * Voraussetzung: Dashboard unter E2E_BASE_URL (Standard http://127.0.0.1:3000).
 * globalSetup setzt Locale DE und Onboarding skipped — Konsole ist erreichbar.
 */
const ASSET_DIR = path.join(
  __dirname,
  "..",
  "..",
  "docs",
  "cursor_execution",
  "49_trust_assets",
);

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

test.describe("Trust & Einstiege (Konsole, authentifiziert)", () => {
  const paths = [
    { name: "help-overview", path: "/console/help" },
    { name: "health-entry", path: "/console/health" },
    { name: "paper-trust", path: "/console/paper" },
    { name: "account-hub", path: "/console/account" },
  ] as const;

  for (const { name, path: p } of paths) {
    test(`${p} lädt mit Vertrauens-/Hilfekontext`, async ({ page }) => {
      const res = await page.goto(p, { waitUntil: "domcontentloaded" });
      expect(res?.ok(), `${p} HTTP ${res?.status()}`).toBeTruthy();
      await expect(page.locator("main.dash-main")).toBeVisible();
      await expect(page.locator(".console-trust-banner")).toBeVisible();
      const buf = await page.screenshot({ fullPage: false });
      tryWriteScreenshot(`${name}-desktop.png`, buf);
    });
  }
});

test.describe("Sprach-Tor & Onboarding (ohne StorageState)", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("Willkommen zeigt Sprachwahl und Paper/Shadow/Live-Kontext", async ({
    browser,
  }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    const res = await page.goto("/welcome", { waitUntil: "domcontentloaded" });
    expect(res?.ok()).toBeTruthy();
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      /Sprache|Choose your language/i,
    );
    await expect(page.locator(".welcome-card")).toContainText(/Paper/i);
    const buf = await page.screenshot({ fullPage: false });
    tryWriteScreenshot("welcome-gate.png", buf);
    await ctx.close();
  });

  test("Onboarding-Seite erreichbar", async ({ browser }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    const res = await page.goto("/onboarding", {
      waitUntil: "domcontentloaded",
    });
    expect(res?.ok()).toBeTruthy();
    await expect(page.locator(".onboarding-card")).toBeVisible();
    const buf = await page.screenshot({ fullPage: false });
    tryWriteScreenshot("onboarding-de.png", buf);
    await ctx.close();
  });
});
