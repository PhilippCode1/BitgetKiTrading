import { expect, test } from "@playwright/test";

/**
 * Broken-interaction / dead-link detector (Sprint 1 Prompt B):
 * alle in der Sidebar sichtbaren internen Ziele traversieren, plus Kern-Startpfade.
 * Zusaetzlich: feste kritische Konsole-Pfade + sichere Klicks (kein LLM-Submit).
 * Scheitert bei HTTP-Fehlerantwort, fehlendem main, harten Fehlerbannern oder pageerror.
 */
async function primeConsoleSession(page: import("@playwright/test").Page) {
  await page.goto("/console/account");
  await page.waitForLoadState("domcontentloaded");
}

function stripHash(href: string): string {
  const i = href.indexOf("#");
  return i === -1 ? href : href.slice(0, i);
}

/** Pfad ohne Query (fuer Routing-Typ). */
function pathOnly(href: string): string {
  const q = href.indexOf("?");
  return q === -1 ? href : href.slice(0, q);
}

async function assertPageHealthyForHref(
  page: import("@playwright/test").Page,
  href: string,
): Promise<void> {
  const path = pathOnly(stripHash(href));
  if (path === "/" || path === "") {
    await expect(page.locator("#top, main").first()).toBeVisible();
    return;
  }
  if (path.startsWith("/onboarding")) {
    await expect(page.locator(".public-header")).toBeVisible();
    await expect(page.locator("main")).toBeVisible();
    return;
  }
  if (path.startsWith("/console")) {
    await expect(page.locator(".dash-sidebar")).toBeVisible();
    await expect(page.locator("main")).toBeVisible();
    await expect(page.locator("main .msg-err")).toHaveCount(0);
    await expect(page.locator("main .console-fetch-notice--alert")).toHaveCount(
      0,
    );
    return;
  }
  await expect(page.locator("main")).toBeVisible();
}

/** Kritische Operator-Pfade unabhaengig von Sidebar-Reihenfolge (Release-Gate-Paritaet). */
const CRITICAL_CONSOLE_PATHS: string[] = [
  "/console",
  "/console/terminal",
  "/console/signals",
  "/console/market-universe",
  "/console/health",
  "/console/diagnostics",
  "/console/self-healing",
  "/console/live-broker",
  "/console/ops",
  "/console/learning",
  "/console/no-trade",
  "/console/integrations",
  "/console/usage",
  "/console/help",
  "/console/account",
  "/console/paper",
  "/console/news",
  "/console/strategies",
  "/console/approvals",
  "/console/capabilities",
];

test.describe("Broken interactions — Sidebar-Links (Konsole)", () => {
  test.beforeEach(async ({ page }) => {
    await primeConsoleSession(page);
  });

  test("Jeder Sidebar-Link: 2xx, Shell, keine pageerror, keine harten Banner", async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (err) => {
      pageErrors.push(err.message);
    });

    await page.goto("/console", { waitUntil: "domcontentloaded" });
    await expect(page.locator(".dash-sidebar")).toBeVisible();

    const rawHrefs = await page.$$eval(
      'aside.dash-sidebar a[href^="/"]',
      (anchors) =>
        anchors
          .map((a) => a.getAttribute("href"))
          .filter((h): h is string => Boolean(h)),
    );
    const hrefs = [...new Set(rawHrefs.map(stripHash))];
    expect(
      hrefs.length,
      "Sidebar muss interne Links enthalten",
    ).toBeGreaterThan(3);

    for (const href of hrefs) {
      pageErrors.length = 0;
      const res = await page.goto(href, { waitUntil: "domcontentloaded" });
      expect(res?.ok(), `${href} HTTP ${res?.status() ?? "?"}`).toBeTruthy();
      await assertPageHealthyForHref(page, href);
      expect(
        pageErrors,
        `${href}: unhandled pageerror: ${pageErrors.join(" | ")}`,
      ).toEqual([]);
    }
  });
});

test.describe("Broken interactions — kritische Konsole-Pfade (fest)", () => {
  test.beforeEach(async ({ page }) => {
    await primeConsoleSession(page);
  });

  test("Jeder Pfad in CRITICAL_CONSOLE_PATHS: 2xx, Shell, keine pageerror", async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));

    for (const path of CRITICAL_CONSOLE_PATHS) {
      pageErrors.length = 0;
      const res = await page.goto(path, { waitUntil: "domcontentloaded" });
      expect(res?.ok(), `${path} HTTP ${res?.status() ?? "?"}`).toBeTruthy();
      await assertPageHealthyForHref(page, path);
      expect(
        pageErrors,
        `${path}: pageerror: ${pageErrors.join(" | ")}`,
      ).toEqual([]);
    }
  });
});

test.describe("Broken interactions — sichere Klicks (Kernoberflaechen)", () => {
  test.beforeEach(async ({ page }) => {
    await primeConsoleSession(page);
  });

  test("Terminal: Daten aktualisieren + technische Details ohne pageerror", async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));

    const res = await page.goto("/console/terminal", {
      waitUntil: "domcontentloaded",
    });
    expect(res?.ok()).toBeTruthy();
    await expect(page.locator("main header.toolbar")).toBeVisible({
      timeout: 60_000,
    });

    const reload = page
      .getByTestId("live-terminal-reload")
      .or(
        page.getByRole("button", {
          name: /Refresh data|Daten aktualisieren/i,
        }),
      );
    await expect(reload).toBeVisible({ timeout: 30_000 });
    await reload.click();
    await page.waitForTimeout(1500);
    expect(pageErrors, `reload: ${pageErrors.join(" | ")}`).toEqual([]);

    const techSummary = page.locator(
      "main details.live-terminal-tech-details summary",
    );
    await expect(techSummary).toBeVisible({ timeout: 15_000 });
    await techSummary.click();
    await expect(
      page.locator("main .live-terminal-tech-details__body"),
    ).toBeVisible();
    expect(pageErrors, `details: ${pageErrors.join(" | ")}`).toEqual([]);
  });

  test("Signale: Zeitfenster-Link (5m) navigiert ohne pageerror", async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));

    const res = await page.goto("/console/signals", {
      waitUntil: "domcontentloaded",
    });
    expect(res?.ok()).toBeTruthy();
    await expect(page.locator(".dash-sidebar")).toBeVisible();

    const tf5 = page.getByRole("link", { name: "5m", exact: true }).first();
    await expect(tf5).toBeVisible({ timeout: 60_000 });
    await tf5.click();
    await page.waitForLoadState("domcontentloaded");
    await assertPageHealthyForHref(page, "/console/signals");
    expect(pageErrors, `signals 5m: ${pageErrors.join(" | ")}`).toEqual([]);
  });

  test("Health: Quick-Action Diagnose-Link (ohne LLM-Submit)", async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));

    const res = await page.goto("/console/health", {
      waitUntil: "domcontentloaded",
    });
    expect(res?.ok()).toBeTruthy();
    await expect(page.locator("main h1").first()).toBeVisible({
      timeout: 60_000,
    });

    const diagLink = page
      .getByRole("link", {
        name: /Open diagnostic|Diagnose öffnen|Diagnose/i,
      })
      .first();
    await expect(diagLink).toBeVisible({ timeout: 30_000 });
    await diagLink.click();
    await page.waitForLoadState("domcontentloaded");
    await expect(page).toHaveURL(/[?&]diagnostic=1/);
    await assertPageHealthyForHref(page, "/console/health");
    expect(pageErrors, `health diagnostic link: ${pageErrors.join(" | ")}`).toEqual(
      [],
    );
  });
});

test.describe("Broken interactions — oeffentliche Einstiegspunkte", () => {
  test("Startseite /", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (e) => pageErrors.push(e.message));
    const res = await page.goto("/", { waitUntil: "domcontentloaded" });
    expect(res?.ok()).toBeTruthy();
    await expect(page.locator("#top, main").first()).toBeVisible();
    expect(pageErrors).toEqual([]);
  });

  test("/welcome laedt (Sprach-Gate)", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (e) => pageErrors.push(e.message));
    const res = await page.goto("/welcome", { waitUntil: "domcontentloaded" });
    expect(res?.ok()).toBeTruthy();
    await expect(page.locator("main.welcome-gate")).toBeVisible();
    expect(pageErrors).toEqual([]);
  });
});
