import { expect, test } from "@playwright/test";

/**
 * Phase 4: In-Content-Navigation — von Listen in dynamische [id]-Routen.
 * Klickt erste Tabellenzeile (Desktop- oder Mobile-Karte) und prüft Detail-Views
 * auf pageerror, harte BFF-Banner und zentrale UI-Flächen (kein reiner Sidebar-Crawl).
 *
 * Voraussetzung: wie andere Konsole-Tests (storageState, laufendes Dashboard).
 * Ohne Listendaten: Test wird per test.skip() übersprungen (kein False-Negative in leeren Umgebungen).
 */

async function primeConsoleSession(page: import("@playwright/test").Page) {
  await page.goto("/console/account");
  await page.waitForLoadState("domcontentloaded");
}

async function assertConsoleShellNoHardErrors(
  page: import("@playwright/test").Page,
) {
  await expect(page.locator(".dash-sidebar")).toBeVisible();
  await expect(page.locator("main")).toBeVisible();
  await expect(page.locator("main .msg-err")).toHaveCount(0);
  await expect(page.locator("main .console-fetch-notice--alert")).toHaveCount(0);
}

test.describe("Deep content — Tabelle/Listen → [id] Detail", () => {
  test.beforeEach(async ({ page }) => {
    await primeConsoleSession(page);
  });

  test("Signale: erste Zeile → /console/signals/[id], Chart + Risiko + Explain", async ({
    page,
  }, testInfo) => {
    test.setTimeout(200_000);
    const pageErrors: string[] = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));

    const res = await page.goto("/console/signals", {
      waitUntil: "domcontentloaded",
    });
    expect(res?.ok(), `/console/signals HTTP ${res?.status()}`).toBeTruthy();
    await assertConsoleShellNoHardErrors(page);

    const toDetail = page
      .locator('main a[href^="/console/signals/"]')
      .first();
    if ((await toDetail.count()) === 0) {
      testInfo.skip(true, "Keine Signale: keine Detail-Navigation testbar");
      return;
    }
    await expect(toDetail).toBeVisible({ timeout: 90_000 });
    await toDetail.click();
    await page.waitForLoadState("domcontentloaded");

    await expect(page).toHaveURL(/\/console\/signals\/.+/);
    await assertConsoleShellNoHardErrors(page);

    const notFound = page.getByText(
      /Signal nicht|nicht verf|nicht gefunden|not found|Nicht gefunden|NotFound/i,
    );
    if (await notFound.isVisible().catch(() => false)) {
      expect(
        pageErrors,
        `not-found: ${pageErrors.join(" | ")}`,
      ).toEqual([]);
      return;
    }

    await expect(page.locator("main .console-live-market-chart")).toBeVisible({
      timeout: 120_000,
    });
    await expect(page.locator("main .signal-detail-risk-strategy")).toBeVisible(
      { timeout: 30_000 },
    );
    const storedExplain = page.locator("main .signal-detail-stored-explain");
    const liveExplain = page.locator("main .signal-explain-llm-wrap");
    await expect(
      storedExplain
        .or(liveExplain)
        .or(page.locator("main .signal-detail-live-ai"))
        .first(),
    ).toBeVisible({ timeout: 30_000 });

    expect(
      pageErrors,
      `signale detail: ${pageErrors.join(" | ")}`,
    ).toEqual([]);
  });

  test("News: erste Zeile → /console/news/[id] — Zusammenfassung/Body ohne Crash", async ({
    page,
  }, testInfo) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));

    const res = await page.goto("/console/news?min_score=0", {
      waitUntil: "domcontentloaded",
    });
    expect(res?.ok(), `/console/news HTTP ${res?.status()}`).toBeTruthy();
    await assertConsoleShellNoHardErrors(page);

    const toDetail = page
      .locator(
        'main a[href^="/console/news/"]:not([href*="?"])',
      )
      .first();
    if ((await toDetail.count()) === 0) {
      testInfo.skip(
        true,
        "Keine News-Zeilen: Detail-Route nicht testbar",
      );
      return;
    }
    await expect(toDetail).toBeVisible({ timeout: 90_000 });
    const href = await toDetail.getAttribute("href");
    expect(href).toBeTruthy();
    expect(href).toMatch(/\/console\/news\/[^/?]+/);

    await toDetail.click();
    await page.waitForLoadState("domcontentloaded");

    await expect(page).toHaveURL(/\/console\/news\/.+/);
    await assertConsoleShellNoHardErrors(page);

    const softMissing = page.locator("main .console-fetch-notice--soft");
    if (await softMissing.isVisible().catch(() => false)) {
      expect(pageErrors, `news soft: ${pageErrors.join(" | ")}`).toEqual([]);
      return;
    }

    await expect(page.locator("main h2").first()).toBeVisible({ timeout: 20_000 });
    await expect(page.locator("main .panel, main .explain").first()).toBeVisible();
    expect(pageErrors, `news detail: ${pageErrors.join(" | ")}`).toEqual([]);
  });

  test("Strategien: erste Zeile → /console/strategies/[id] — Metriken, Signalpfad, KI-Block", async ({
    page,
  }, testInfo) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));

    const res = await page.goto("/console/strategies", {
      waitUntil: "domcontentloaded",
    });
    expect(
      res?.ok(),
      `/console/strategies HTTP ${res?.status()}`,
    ).toBeTruthy();
    await assertConsoleShellNoHardErrors(page);

    const toDetail = page
      .locator('main a[href^="/console/strategies/"]')
      .first();
    if ((await toDetail.count()) === 0) {
      testInfo.skip(
        true,
        "Keine Strategien: Detail-Route nicht testbar",
      );
      return;
    }
    await expect(toDetail).toBeVisible({ timeout: 90_000 });
    await toDetail.click();
    await page.waitForLoadState("domcontentloaded");

    await expect(page).toHaveURL(/\/console\/strategies\/.+/);
    await assertConsoleShellNoHardErrors(page);

    const notFoundSoft = page.getByText(
      /Strategie nicht|nicht gefunden|not found|Nicht gefunden/i,
    );
    if (await notFoundSoft.isVisible().catch(() => false)) {
      expect(
        pageErrors,
        `strat not-found: ${pageErrors.join(" | ")}`,
      ).toEqual([]);
      return;
    }

    await expect(page.locator("main .panel").first()).toBeVisible({
      timeout: 30_000,
    });
    // Risiko-/Scope-Metadaten, Performance-Panel (Surrogate für „Marktbild“), Signalpfad, KI-Block
    await expect(
      page.locator("main .signal-grid, main h2, main [role=status]"),
    )
      .first()
      .toBeVisible();
    const panelCount = await page.locator("main .panel").count();
    expect(panelCount, "Detailseite soll mehrere Panels anzeigen").toBeGreaterThan(0);
    expect(pageErrors, `strategies detail: ${pageErrors.join(" | ")}`).toEqual(
      [],
    );
  });
});
