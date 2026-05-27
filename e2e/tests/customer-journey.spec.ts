import { expect, test } from "@playwright/test";

import { setCustomerPortalSessionCookies } from "../lib/portal-session";

test.describe("Endkunden — Deep Journey", () => {
  test.beforeEach(async ({ page, baseURL }) => {
    const token = await setCustomerPortalSessionCookies(page, baseURL);
    if (!token) {
      test.skip(
        true,
        "GATEWAY_JWT_SECRET fehlt (E2E: .env.local oder Env, identisch zum Dashboard)",
      );
    }
  });

  test("Kunde: /console/health blockiert, Portal Performance + Detail, Chart, keine Operator-UI, saubere Konsole", async ({
    page,
    baseURL,
  }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });
    page.on("pageerror", (err) => {
      pageErrors.push(err.message);
    });

    await page.goto(`${baseURL}/console/health`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page).toHaveURL(new RegExp("/portal/?$"));

    await page.goto(`${baseURL}/portal`, { waitUntil: "domcontentloaded" });
    await expect(
      page.locator('[data-app-region="customer-portal"]'),
    ).toBeVisible();
    await expect(
      page.locator('aside[data-portal="customer"]'),
    ).toBeVisible();
    await expect(page.locator('[data-e2e="operator-sidebar"]')).toHaveCount(0);
    await expect(
      page.locator('nav a[href^="/console/"]'),
    ).toHaveCount(0);
    await expect(page.locator(".operator-explain-panel")).toHaveCount(0);

    await page.goto(`${baseURL}/portal/performance`, {
      waitUntil: "domcontentloaded",
    });
    await expect(
      page.getByTestId("customer-performance-table"),
    ).toBeVisible();
    const detailLinks = page
      .locator('[data-e2e-performance-row] a[href^="/portal/performance/"]')
      .or(page.getByRole("link", { name: /Details/i }));
    if ((await detailLinks.count()) > 0) {
      await detailLinks.first().click();
      await expect(page).toHaveURL(/\/portal\/performance\/[^/]+$/);
      await expect(
        page.getByTestId("customer-performance-detail"),
      ).toBeVisible();
    }

    const hasCanvas = await page.locator("main canvas").count();
    const hasChartSvg = await page.locator("main svg").count();
    expect(
      hasCanvas + hasChartSvg,
      "Erwartet: lightweight-charts (canvas) und/oder SVG in main",
    ).toBeGreaterThan(0);

    expect(
      pageErrors,
      `pageerror: ${pageErrors.join(" | ")}`,
    ).toEqual([]);
    expect(
      consoleErrors,
      `console error: ${consoleErrors.join(" | ")}`,
    ).toEqual([]);
  });
});
