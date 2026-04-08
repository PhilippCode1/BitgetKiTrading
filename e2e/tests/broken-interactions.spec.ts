import { expect, test } from "@playwright/test";

/**
 * Broken-interaction / dead-link detector (Sprint 1 Prompt B):
 * alle in der Sidebar sichtbaren internen Ziele traversieren, plus Kern-Startpfade.
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
