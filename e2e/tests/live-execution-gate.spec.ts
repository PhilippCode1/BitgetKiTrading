/**
 * E2E-Beweise fuer die Echtgeld-Barriere (Execution Gate) und den Go-Live-
 * Workflow im Kundenportal.
 *
 * Start (lokal):
 *   pnpm exec playwright test e2e/tests/live-execution-gate.spec.ts
 *
 * Voraussetzungen:
 *   - Dashboard laeuft (E2E_BASE_URL, Default http://127.0.0.1:3000).
 *   - GATEWAY_JWT_SECRET in .env.local oder ENV gesetzt
 *     (identisch zum Dashboard-Prozess).
 *   - Testfall C: ENABLE_E2E_FIXTURES=true im Dashboard-Prozess
 *     (SSR-Ribbon-Fixture, nur Dev/Test).
 *
 * Strategie:
 *   Portal-JWT direkt als HttpOnly-Cookie (wie customer-journey.spec.ts).
 *   BFF-Route `live-execution/enable` per `page.route` gemockt.
 */

import { expect, test, type Page } from "@playwright/test";

import {
  setCustomerPortalSessionCookies,
} from "../lib/portal-session";

const ENABLE_LIVE_URL_GLOB =
  "**/api/dashboard/commerce/customer/live-execution/enable";

const PREFLIGHT_URL_GLOB =
  "**/api/dashboard/commerce/customer/live-execution/preflight";

type MockResponse = {
  status: number;
  body: Record<string, unknown>;
};

async function mockLiveExecutionPreflight(
  page: Page,
  body: Record<string, unknown>,
): Promise<void> {
  await page.unroute(PREFLIGHT_URL_GLOB).catch(() => undefined);
  await page.route(PREFLIGHT_URL_GLOB, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
}

async function mockLiveExecutionResponse(
  page: Page,
  response: MockResponse,
): Promise<void> {
  await page.unroute(ENABLE_LIVE_URL_GLOB).catch(() => undefined);
  await page.route(ENABLE_LIVE_URL_GLOB, async (route) => {
    await route.fulfill({
      status: response.status,
      contentType: "application/json",
      body: JSON.stringify(response.body),
    });
  });
}

async function gotoTradingPage(
  page: Page,
  baseURL: string | undefined,
): Promise<void> {
  const base = baseURL ?? "http://127.0.0.1:3000";
  await page.goto(`${base}/portal/trading`, { waitUntil: "load" });
  await expect(page.locator('[data-e2e="customer-portal-trading"]')).toBeVisible();
}

async function openConfirmModal(page: Page): Promise<void> {
  const btn = page.locator('[data-e2e="enable-live-btn"]');
  await expect(btn).toBeVisible();
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await btn.click();
    try {
      await expect(page.locator('[data-e2e="modal-confirm-checkbox"]')).toBeVisible({
        timeout: 8_000,
      });
      return;
    } catch {
      if (attempt === 2) {
        throw new Error("Go-Live-Modal oeffnet nicht (React-Hydration?)");
      }
    }
  }
}

async function confirmModal(page: Page): Promise<void> {
  await page.locator('[data-e2e="modal-confirm-checkbox"]').check();
  await page.locator('[data-e2e="modal-confirm-btn"]').click();
}

test.describe("Echtgeld-Sperre & Go-Live Workflow", () => {
  test.beforeEach(async ({ page, baseURL }) => {
    const token = await setCustomerPortalSessionCookies(page, baseURL);
    if (!token) {
      test.skip(
        true,
        "GATEWAY_JWT_SECRET fehlt (siehe .env.local / ENV). Mock-Login ohne Secret nicht moeglich.",
      );
    }
  });

  test("Testfall A0: Preflight-Blocker deaktivieren Go-Live-Button", async ({
    page,
    baseURL,
  }) => {
    await mockLiveExecutionPreflight(page, {
      step_up_required: false,
      ready: false,
      blockers: ["MISSING_API_KEYS", "CONTRACT_NOT_SIGNED"],
    });
    await gotoTradingPage(page, baseURL);
    await expect(page.locator('[data-e2e="go-live-preflight-blockers"]')).toBeVisible();
    await expect(page.locator('[data-e2e="enable-live-btn"]')).toBeDisabled();
  });

  test("Testfall A: Gateway 400 MISSING_API_KEYS landet als nutzerfreundlicher Fehler", async ({
    page,
    baseURL,
  }) => {
    await gotoTradingPage(page, baseURL);
    await mockLiveExecutionResponse(page, {
      status: 400,
      body: {
        detail: { error: "MISSING_API_KEYS", message: "Bitget API-Keys fehlen" },
      },
    });

    await openConfirmModal(page);
    const responsePromise = page.waitForResponse((res) =>
      res.url().includes("/live-execution/enable"),
    );
    await confirmModal(page);
    const response = await responsePromise;
    expect(response.status()).toBe(400);

    await expect(
      page.getByText(/API-Schl(ü|ue)ssel fehlen/i),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Einstellungen|Settings/i }),
    ).toBeVisible();
  });

  test("Testfall A2: CONTRACT_NOT_SIGNED zeigt Vertragshinweis", async ({
    page,
    baseURL,
  }) => {
    await gotoTradingPage(page, baseURL);
    await mockLiveExecutionResponse(page, {
      status: 400,
      body: {
        detail: { error: "CONTRACT_NOT_SIGNED", message: "Kein Vertrag" },
      },
    });
    await openConfirmModal(page);
    await confirmModal(page);
    await expect(page.getByText(/Vertrag fehlt/i)).toBeVisible();
  });

  test("Testfall A3: INSUFFICIENT_BALANCE zeigt Mindestbetrag und Billing-Link", async ({
    page,
    baseURL,
  }) => {
    await gotoTradingPage(page, baseURL);
    await mockLiveExecutionResponse(page, {
      status: 400,
      body: {
        detail: {
          error: "INSUFFICIENT_BALANCE",
          min: "50",
          message: "Zu geringes Guthaben",
        },
      },
    });
    await openConfirmModal(page);
    await confirmModal(page);
    await expect(
      page.getByText(/Unzureichendes Guthaben.*50 USD/i),
    ).toBeVisible();
  });

  test("Testfall A4: INVALID_API_KEYS zeigt Fehlermeldung fuer ungueleltige Keys", async ({
    page,
    baseURL,
  }) => {
    await gotoTradingPage(page, baseURL);
    await mockLiveExecutionResponse(page, {
      status: 400,
      body: {
        detail: {
          error: "INVALID_API_KEYS",
          message: "Bitget API-Keys ungueltig",
        },
      },
    });
    await openConfirmModal(page);
    await confirmModal(page);
    await expect(
      page.getByText(/Ung(ü|ue)ltige API-Schl(ü|ue)ssel/i),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Einstellungen|Settings/i }),
    ).toBeVisible();
  });

  test("Testfall B: Go-Live erfolgreich (HTTP 200) zeigt Success-Banner", async ({
    page,
    baseURL,
  }) => {
    await gotoTradingPage(page, baseURL);
    await mockLiveExecutionResponse(page, {
      status: 200,
      body: { status: "ok", live_trading_allowed: true },
    });

    await openConfirmModal(page);
    const confirmBtn = page.locator('[data-e2e="modal-confirm-btn"]');
    await expect(confirmBtn).toBeDisabled();
    await page.locator('[data-e2e="modal-confirm-checkbox"]').check();
    await expect(confirmBtn).toBeEnabled();

    const responsePromise = page.waitForResponse((res) =>
      res.url().includes("/live-execution/enable"),
    );
    await confirmBtn.click();
    const response = await responsePromise;
    expect(response.status()).toBe(200);

    await expect(
      page.getByText(/Echtgeld-Handel erfolgreich aktiviert/i),
    ).toBeVisible();
  });

  test("Testfall C: Live-Ribbon ist sichtbar mit E2E-Fixture-Cookie", async ({
    page,
    baseURL,
  }) => {
    await setCustomerPortalSessionCookies(page, baseURL, { liveRibbon: true });
    await gotoTradingPage(page, baseURL);
    await expect(page.locator('[data-e2e="live-ribbon"]')).toBeVisible();
  });
});
