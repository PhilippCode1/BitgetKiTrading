import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

/**
 * E2E gegen laufendes Dashboard (Next) + Gateway im Hintergrund.
 * Start: Stack + Dashboard (z. B. Compose-Port 3000 oder `pnpm --filter @bitget-btc-ai/dashboard dev`), dann:
 *   pnpm e2e:install
 *   pnpm e2e
 *
 * BFF/KI: `DASHBOARD_GATEWAY_AUTHORIZATION` muss im Dashboard-Prozess gesetzt sein
 * (Next laedt .env.local beim Start). Erzeugen: `python scripts/mint_dashboard_gateway_jwt.py
 * --env-file .env.local --update-env-file` - danach Dashboard neu starten.
 *
 * Umgebung: E2E_BASE_URL (Default http://127.0.0.1:3000)
 *
 * globalSetup setzt Onboarding + Locale (siehe e2e/global-setup.ts).
 */
export default defineConfig({
  testDir: "./tests",
  globalSetup: path.join(__dirname, "global-setup.ts"),
  timeout: 150_000,
  expect: { timeout: 25_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "e2e/playwright-report" }],
    ["junit", { outputFile: "e2e/test-results/junit.xml" }],
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:3000",
    storageState: path.join(__dirname, ".auth", "storageState.json"),
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
