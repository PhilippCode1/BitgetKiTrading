import * as path from "node:path";
import { mkdirSync, existsSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { signE2eCustomerPortalJwt } from "../lib/customer-jwt";
import { loadGatewayJwtSecretFromRoot } from "../lib/load-gateway-secret";

const DOSSIER_DIR = path.join(
  __dirname,
  "..",
  "..",
  "docs",
  "cursor_execution",
  "85_run_evidence",
);
// __dirname = e2e/tests → ".." ".." = Repo-Root

const PORTAL_JWT = "bitget_portal_jwt";

test.describe("Run 85 Dossier — UI-Evidenz (P85)", () => {
  test.beforeAll(() => {
    if (!existsSync(DOSSIER_DIR)) {
      mkdirSync(DOSSIER_DIR, { recursive: true });
    }
  });

  test("Operator: /console/health (Health-Grid) Screenshot", async ({ page, baseURL }) => {
    await page.goto(new URL("/console/health", baseURL).toString(), { waitUntil: "networkidle" });
    const title = page.locator("h1, h2").first();
    await expect(title).toBeVisible({ timeout: 60_000 });
    await page.screenshot({ path: path.join(DOSSIER_DIR, "operator_console_health.png"), fullPage: true });
  });

  test("Kunde: Portal-Übersicht + Performance (Screenshots)", async ({ page, baseURL }) => {
    const secret = loadGatewayJwtSecretFromRoot();
    test.skip(!secret, "GATEWAY_JWT_SECRET fehlt (Run85 Portal-Shots)");
    const host = new URL(baseURL || "http://127.0.0.1:3000").hostname;
    const token = await signE2eCustomerPortalJwt(secret);
    await page.context().addCookies([
      {
        name: PORTAL_JWT,
        value: token,
        domain: host,
        path: "/",
        httpOnly: true,
        sameSite: "Lax",
        secure: (baseURL || "").startsWith("https:"),
      },
    ]);
    await page.goto(new URL("/portal", baseURL).toString(), { waitUntil: "domcontentloaded" });
    const h1 = page.locator("h1").first();
    await expect(h1).toBeVisible({ timeout: 30_000 });
    await page.screenshot({ path: path.join(DOSSIER_DIR, "customer_portal_overview.png"), fullPage: true });

    await page.goto(new URL("/portal/performance", baseURL).toString(), { waitUntil: "domcontentloaded" });
    const ph = page.getByRole("heading", { name: /performance|Performance/i });
    if ((await ph.count()) > 0) {
      await expect(ph.first()).toBeVisible({ timeout: 30_000 });
    } else {
      const any = page.locator("main, [role=main], .panel, body").first();
      await expect(any).toBeVisible();
    }
    await page.screenshot({ path: path.join(DOSSIER_DIR, "customer_portal_performance.png"), fullPage: true });
  });
});
