# BROKEN_BUTTONS — Nach Sprint 1 (Prompt B)

## Aenderungen

- **Locale-Spiegel** (`POST /api/dashboard/preferences/locale`): kein leeres `.catch(() => {})` mehr in `I18nProvider` / `WelcomeLanguageClient`. Fehler → `console.warn` mit Praefix `[dashboard]` (sichtbar in Browser-Konsole / Remote-Logging), Hauptfluss (Cookie via `/api/locale`) bleibt erhalten.
- **Tests:** `apps/dashboard/src/lib/client/__tests__/best-effort-fetch.test.ts` (HTTP-Fehler + Netzwerkfehler).

## E2E

- `broken-interactions.spec.ts` fokussiert auf **Navigation/Links**; dedizierte Klick-Matrix fuer Self-Healing / Explain-Submit bleibt **P1-2** (Sprint-Plan).

## Count

| Metrik | Wert |
|--------|------|
| Nachgewiesene tote Buttons | 0 (keine neue Messung ausser Locale-Pfad) |
| Silent-catch Locale-Mirror | behoben |
