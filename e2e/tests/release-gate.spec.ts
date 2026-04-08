import { expect, test } from "@playwright/test";

/**
 * Telegram-Gate: optional Umleitung — Account-Hub stabilisiert Session.
 */
async function primeConsoleSession(page: import("@playwright/test").Page) {
  await page.goto("/console/account");
  await page.waitForLoadState("domcontentloaded");
}

test.describe("Release gate — API & Shell", () => {
  test("edge-status liefert JSON mit gatewayHealth", async ({ request }) => {
    const res = await request.get("/api/dashboard/edge-status");
    expect(res.ok(), `edge-status HTTP ${res.status()}`).toBeTruthy();
    const body = (await res.json()) as Record<string, unknown>;
    expect(body).toHaveProperty("gatewayHealth");
    expect(body).toHaveProperty("edgeDiagnostic");
    expect(body).toHaveProperty("bffV1ProxyServerOnly");
    expect(body).toHaveProperty("supportReference");
  });

  test("BFF Operator-Explain (KI-Pfad, Fake- oder echter Provider)", async ({
    request,
  }) => {
    const res = await request.post("/api/dashboard/llm/operator-explain", {
      data: { question_de: "Was bedeutet Kill-Switch hier in einem Satz?" },
      headers: { "Content-Type": "application/json" },
      timeout: 130_000,
    });
    const raw = await res.text();
    expect(
      res.ok(),
      `operator-explain HTTP ${res.status()} ${raw.slice(0, 400)}`,
    ).toBeTruthy();
    const body = JSON.parse(raw) as Record<string, unknown>;
    expect(body.ok !== false, "Envelope ok").toBeTruthy();
    const result = body.result as Record<string, unknown> | undefined;
    const ex = result?.explanation_de;
    expect(
      typeof ex === "string" && (ex as string).trim().length > 0,
      "explanation_de",
    ).toBeTruthy();
  });
});

test.describe("Release gate — Produktstart", () => {
  test("Startseite / laedt", async ({ page }) => {
    const res = await page.goto("/", { waitUntil: "domcontentloaded" });
    expect(res?.ok()).toBeTruthy();
    await expect(page.locator("#top, main").first()).toBeVisible();
  });
});

test.describe("Release gate — Konsole (Kernseiten)", () => {
  test.beforeEach(async ({ page }) => {
    await primeConsoleSession(page);
  });

  const pathsWithH1 = [
    "/console/health",
    "/console/integrations",
    "/console/signals",
    "/console/learning",
    "/console/live-broker",
    "/console/approvals",
    "/console/ops",
    "/console/usage",
    "/console/account",
    "/console/account/broker",
  ];

  for (const path of pathsWithH1) {
    test(`${path} laedt mit Shell und ohne harte Fehlerbanner`, async ({
      page,
    }) => {
      const res = await page.goto(path, { waitUntil: "domcontentloaded" });
      expect(res?.ok(), `${path} HTTP ${res?.status()}`).toBeTruthy();
      await expect(page.locator(".dash-sidebar")).toBeVisible();
      await expect(page.locator("main")).toBeVisible();
      await expect(page.locator("main h1").first()).toBeVisible();
      await expect(page.locator("main .msg-err")).toHaveCount(0);
      await expect(
        page.locator("main .console-fetch-notice--alert"),
      ).toHaveCount(0);
    });
  }

  test("/console/market-universe — Daten-Lineage Panel sichtbar", async ({
    page,
  }) => {
    const res = await page.goto("/console/market-universe", {
      waitUntil: "domcontentloaded",
    });
    expect(res?.ok()).toBeTruthy();
    await expect(page.locator(".dash-sidebar")).toBeVisible();
    await expect(page.getByTestId("market-universe-lineage")).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.locator("main .msg-err")).toHaveCount(0);
  });

  test("/console/terminal — Chart & Toolbar (Marktbild)", async ({ page }) => {
    const res = await page.goto("/console/terminal", {
      waitUntil: "domcontentloaded",
    });
    expect(res?.ok()).toBeTruthy();
    await expect(page.locator(".dash-sidebar")).toBeVisible();
    await expect(page.locator("main")).toBeVisible();
    await expect(page.locator("main header.toolbar")).toBeVisible();
    const chartOrStack = page.locator(
      "main .terminal-chart-stack, main .terminal-main-chart",
    );
    await expect(chartOrStack.first()).toBeVisible({ timeout: 60_000 });
    await expect(page.locator("main .msg-err")).toHaveCount(0);
    await expect(page.locator("main .console-fetch-notice--alert")).toHaveCount(
      0,
    );
  });

  test("/console/health — Operator-KI-Formular sichtbar", async ({ page }) => {
    await page.goto("/console/health", { waitUntil: "domcontentloaded" });
    const panel = page.locator(".operator-explain-panel").first();
    await expect(panel).toBeVisible({ timeout: 60_000 });
    await expect(panel.locator("textarea").first()).toBeVisible({
      timeout: 60_000,
    });
  });

  test("Konsole-Start /console", async ({ page }) => {
    const res = await page.goto("/console", { waitUntil: "domcontentloaded" });
    expect(res?.ok()).toBeTruthy();
    await expect(page.locator(".dash-sidebar")).toBeVisible();
    await expect(page.locator("main .msg-err")).toHaveCount(0);
  });
});
