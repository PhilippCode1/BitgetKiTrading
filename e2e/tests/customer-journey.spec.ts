import { expect, test } from "@playwright/test";

import { signE2eCustomerPortalJwt } from "../lib/customer-jwt";
import { loadGatewayJwtSecretFromRoot } from "../lib/load-gateway-secret";

const PORTAL_JWT = "bitget_portal_jwt";

async function setCustomerSessionCookie(
  page: import("@playwright/test").Page,
  baseURL: string,
) {
  const secret = loadGatewayJwtSecretFromRoot();
  if (!secret) {
    test.skip(
      true,
      "GATEWAY_JWT_SECRET fehlt (E2E: .env.local oder Env, identisch zum Dashboard)",
    );
    return;
  }
  const token = await signE2eCustomerPortalJwt(secret);
  const host = new URL(baseURL).hostname;
  const secure = new URL(baseURL).protocol === "https:";
  await page.context().addCookies([
    {
      name: PORTAL_JWT,
      value: token,
      domain: host,
      path: "/",
      httpOnly: true,
      sameSite: "Lax",
      secure,
    },
  ]);
}

test.describe("Endkunden — Deep Journey", () => {
  test.beforeEach(async ({ page, baseURL }) => {
    await setCustomerSessionCookie(page, baseURL!);
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

    await page
      .locator('[data-e2e-performance-row="e2e-mock-1"]')
      .getByRole("link", { name: /Details/i })
      .click();
    await expect(page).toHaveURL(/\/portal\/performance\/e2e-mock-1/);
    await expect(
      page.getByTestId("customer-performance-detail"),
    ).toBeVisible();

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
