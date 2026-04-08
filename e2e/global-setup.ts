import fs from "node:fs";
import path from "node:path";
import { chromium, type FullConfig } from "@playwright/test";

/**
 * Setzt Locale- und Onboarding-Cookies (Middleware-Gates), damit /console/* ohne manuelle Klicks erreichbar ist.
 */
export default async function globalSetup(config: FullConfig): Promise<void> {
  const baseURL =
    (config.projects[0]?.use?.baseURL as string | undefined) ||
    process.env.E2E_BASE_URL ||
    "http://127.0.0.1:3000";

  const browser = await chromium.launch();
  const context = await browser.newContext();

  const onb = await context.request.post(`${baseURL}/api/onboarding/status`, {
    data: { status: "skipped" },
    headers: { "Content-Type": "application/json" },
  });
  if (!onb.ok()) {
    await browser.close();
    throw new Error(
      `globalSetup: onboarding status HTTP ${onb.status()} ${await onb.text()}`,
    );
  }

  const loc = await context.request.post(`${baseURL}/api/locale`, {
    data: { locale: "de" },
    headers: { "Content-Type": "application/json" },
  });
  if (!loc.ok()) {
    await browser.close();
    throw new Error(
      `globalSetup: locale HTTP ${loc.status()} ${await loc.text()}`,
    );
  }

  const outDir = path.join(__dirname, ".auth");
  fs.mkdirSync(outDir, { recursive: true });
  const statePath = path.join(outDir, "storageState.json");
  await context.storageState({ path: statePath });
  await browser.close();
}
