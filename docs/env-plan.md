# Environment Plan

Ausfuehrungsmodi **paper / shadow / live** und Broker-Freigaben: `docs/live_broker.md` und `docs/Deploy.md`.

## File Roles

- `.env.example`: deduplicated key catalog for the whole repo. It documents every committed example key once and is not the runnable profile to copy first.
- `.env.local.example`: local-only development profile. Demo, fixture, and fake provider paths are allowed here.
- `.env.shadow.example`: production-like shadow profile. Real hosts only, no demo defaults, no fixture mode, no fake providers, and no real live order submit.
- `.env.production.example`: production profile. Real hosts only, no demo defaults, no fixture mode, no fake providers, no `pnpm dev` assumptions. Safe default for the current repo reality is still `EXECUTION_MODE=shadow`.
- `.env.test.example`: deterministic test profile with isolated test DSNs and test-safe fake/fixture toggles.
- `.env.local`, `.env.shadow`, `.env.production`, `.env.test`: ignored runtime copies with real values.

## Separation Rules

- Keep exchange, database, Telegram, and LLM secrets outside the repository.
- Only `NEXT_PUBLIC_` variables may be consumed by frontend code.
- Local and test profiles may carry demo/fake/fixture toggles; shadow and production may not.
- Production and shadow must use real hosts for `APP_BASE_URL`, `FRONTEND_URL`, `DATABASE_URL`, `REDIS_URL`, and internal health endpoints.
- Canonical execution and auth switches are `EXECUTION_MODE`, `STRATEGY_EXEC_MODE`, `SHADOW_TRADE_ENABLE`, `LIVE_TRADE_ENABLE`, and `API_AUTH_MODE`.
- The committed examples document the mandatory control groups for live, risk, model ops, and security.

## Required Profile Intent

### Local

- `PRODUCTION=false`
- `EXECUTION_MODE=paper`
- `STRATEGY_EXEC_MODE=manual`
- `SHADOW_TRADE_ENABLE=false`
- `LIVE_TRADE_ENABLE=false`
- `API_AUTH_MODE=none`
- `BITGET_DEMO_ENABLED=true`
- `PAPER_SIM_MODE=true`
- `PAPER_CONTRACT_CONFIG_MODE=fixture`
- `NEWS_FIXTURE_MODE=true`
- `LLM_USE_FAKE_PROVIDER=true`
- `TELEGRAM_DRY_RUN=true`

### Shadow

- `PRODUCTION=true`
- `EXECUTION_MODE=shadow`
- `STRATEGY_EXEC_MODE=manual`
- `API_AUTH_MODE=api_key`
- `SHADOW_TRADE_ENABLE=true`
- `BITGET_DEMO_ENABLED=false`
- `PAPER_SIM_MODE=false`
- `PAPER_CONTRACT_CONFIG_MODE=live`
- `NEWS_FIXTURE_MODE=false`
- `LLM_USE_FAKE_PROVIDER=false`
- `LIVE_TRADE_ENABLE=false`

### Production

- `PRODUCTION=true`
- `DEBUG=false`
- `LOG_FORMAT=json`
- `VAULT_MODE=hashicorp|aws`
- `EXECUTION_MODE=shadow` until a real live trade gate exists
- `STRATEGY_EXEC_MODE=manual`
- `SHADOW_TRADE_ENABLE=true`
- `LIVE_TRADE_ENABLE=false`
- `API_AUTH_MODE=api_key`
- `BITGET_DEMO_ENABLED=false`
- `PAPER_SIM_MODE=false`
- `PAPER_CONTRACT_CONFIG_MODE=live`
- `NEWS_FIXTURE_MODE=false`
- `LLM_USE_FAKE_PROVIDER=false`
- `TELEGRAM_DRY_RUN=false`
- `NODE_ENV=production`
- `NEXT_PUBLIC_ENABLE_ADMIN=false`

### Test

- `PRODUCTION=false`
- `APP_ENV=test`
- `CI=true`
- `NODE_ENV=test`
- `EXECUTION_MODE=paper`
- `STRATEGY_EXEC_MODE=manual`
- `SHADOW_TRADE_ENABLE=false`
- `LIVE_TRADE_ENABLE=false`
- `API_AUTH_MODE=none`
- `TEST_DATABASE_URL` and `TEST_REDIS_URL` point to test infrastructure
- Deterministic fake and fixture paths stay test-only

## Demo Trading Notes

- Demo REST uses demo API keys together with the `paptrading: 1` header.
- Demo WebSocket traffic uses the `wspap.bitget.com` domains.
- Demo values belong in local and test only.

## Rotation Policy

- If a secret is exposed in chat, logs, or Git history, rotate it immediately.
- Treat every `*.example` file as documentation only; never place real values there.
