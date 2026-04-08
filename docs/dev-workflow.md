# Development Workflow

## Branching Model

- `main`: stable branch.
- `dev`: integration branch.
- `feat/<name>`: feature branches for focused work.

## Formatting And Style

- TypeScript formatting uses Prettier from the workspace root.
- Python formatting uses Black.
- Python linting uses Ruff.
- Prefer strict typing in both TypeScript and Python.

## Expected Checks

- `pnpm format:check`
- `pnpm lint`
- `python -m compileall services/api-gateway/src`
- `python -m compileall services/feature-engine/src`
- `python -m compileall services/structure-engine/src`
- `python -m compileall services/drawing-engine/src`
- `python -m compileall services/signal-engine/src`
- `python -m compileall shared/python/src`
- `python -m compileall services/market-stream/src`
- `python infra/migrate.py`
- `pytest -q shared/python`
- `pytest -q tests/feature_engine`
- `pytest -q tests/structure_engine`
- `pytest -q tests/drawing_engine`
- `pytest -q tests/signal_engine`
- `pytest -q services/market-stream`
- `python -m unittest discover -s tests/market-stream -p "test_*.py"`
- `python -m ruff check services shared`
- `python -m black --check services shared`

## Development Rules

- Neue Funktionen direkt hinter Feature-Flags und Profilen (`paper` / `shadow` / `live`) entwickeln; keine Fake-/Demo-Defaults in Shadow- oder Produktionsprofilen.
- Secrets niemals ins Repo oder in Browser-Runtimes; Laufzeit nur Vault/KMS/Secret Manager.
- Jede neue oder geaenderte ENV-Variable: `.env.example`, betroffene `*.example`-Profile und `infra/service-manifest.yaml` mitziehen.
- Tests mit dem gleichen Modul mitliefern oder erweitern (`docs/testing_guidelines.md`).
- Produktionscontainer: Dashboard `next build` (standalone) + `node build/standalone/.../server.js`, kein `pnpm dev` und kein `next start` im Release-Image.

## Docker Compose Quickstart

- Preferred with local overrides: `docker compose --env-file .env.local up -d --build`
- Safe fallback without local secrets: `docker compose up -d --build`
- Check running containers: `docker compose ps`
- Verify API health: `curl -s http://localhost:8000/health`
- Verify dashboard response headers: `curl -s -I http://localhost:3000`
- Inspect recent API logs: `docker compose logs --tail=100 api-gateway`
- Inspect recent dashboard logs: `docker compose logs --tail=100 dashboard`
- Stop and remove containers: `docker compose down`

## Tests

- Richtlinien: `docs/testing_guidelines.md`
- Schnell: `pytest tests shared/python/tests -m "not integration"`
- Produktion/Deploy: `docs/Deploy.md`, `docs/LaunchChecklist.md`
