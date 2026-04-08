# E2E / Browser-Tests

Die **kanonischen** Playwright-Specs liegen unter **`e2e/`** (nicht in diesem Ordner):

| Pfad                             | Inhalt                                                                 |
| -------------------------------- | ---------------------------------------------------------------------- |
| `e2e/playwright.config.ts`       | Chromium, Timeouts, `globalSetup`                                      |
| `e2e/global-setup.ts`            | Locale + Onboarding-Cookies (Middleware-Gates)                         |
| `e2e/tests/release-gate.spec.ts` | Nutzerreisen: API, Startseite, Konsole, Terminal/Chart, KI-BFF, Broker |

## Lokaler Lauf

Voraussetzung: Dashboard erreichbar (z. B. Compose-Dienst auf Port **3000** oder `pnpm --filter @bitget-btc-ai/dashboard dev`).

```bash
pnpm install
pnpm e2e:install
pnpm e2e
# oder explizit:
E2E_BASE_URL=http://127.0.0.1:3000 pnpm exec playwright test -c e2e/playwright.config.ts
```

## Release-Gate (HTTP + optional E2E)

```bash
# Stack + .env.local: Gateway-Smokes, rc_health, KI-Orchestrator, Dashboard-HTML-Probes
python scripts/release_gate.py

# Zusätzlich Playwright (Dashboard muss laufen)
pnpm release:gate:full
```

CI: Job **`compose_healthcheck`** in `.github/workflows/ci.yml` führt nach Health + KI-Smoke die **Playwright**-Specs aus.

Weitere technische Gates: **`docs/ci_release_gates.md`**.
