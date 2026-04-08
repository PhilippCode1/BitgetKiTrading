# Branch- und Commit-Policy (P0 Baseline)

**Zweck:** Reproduzierbare Audits und CI (`AUDIT_REPORT` verlangt Commit-Hash).

## Regeln

1. **Default-Branch:** `main` oder `master` (CI laeuft auf beidem laut `.github/workflows/ci.yml`).
2. **Jede Aenderung:** Commit mit klarer Message (imperativ, deutsch oder englisch konsistent im Team).
3. **Vor Merge:** `pnpm check-types`, `pnpm test` (bzw. Turbo), Python-Job gruen, oder dokumentierter Ausnahme-Grund in PR.
4. **Tags:** Release `v*` optional; Audit-Laeufe referenzieren `git rev-parse HEAD`.

## Erst-Commit (einmalig)

Wenn das Repo noch ohne Commit ist:

```bash
git add -A
git commit -m "chore: initial import bitget-btc-ai monorepo"
```

Danach nie force-push auf den Default-Branch ohne Notfallprotokoll.
