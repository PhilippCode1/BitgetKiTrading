# Single-Admin Access Control (Philipp-only)

## Zielbild

`bitget-btc-ai` ist private Single-Admin-Software fuer Philipp Crljic.
Es gibt keine Team-RBAC-, Kunden- oder Tenant-Bedienlogik als aktiven Produktpfad.
Trotzdem gelten harte Sicherheitsregeln fuer Gateway, BFF und interne Service-Keys.

## Verbindliche Regeln

1. Sensitive Gateway- und BFF-Routen nur mit Auth.
2. Browser sieht keine internen Secrets (`DASHBOARD_GATEWAY_AUTHORIZATION`, `INTERNAL_API_KEY`, JWT-Secrets).
3. `DASHBOARD_GATEWAY_AUTHORIZATION` ist serverseitig (BFF), nie `NEXT_PUBLIC_*`.
4. Legacy-Admin-Token (`GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN`) in Production nicht aktiv.
5. Single-Admin-Subject ist bindend (`GATEWAY_SUPER_ADMIN_SUBJECT`).
6. Keine Rollen-Simulation via Query-Parameter.
7. Auth-Fehler deutsch, ohne Secret-Leak.
8. Gastmodus darf keine Trading-/Admin-Daten erhalten.

## Architekturpfad

- Browser -> Dashboard BFF (`apps/dashboard/src/app/api/dashboard/*`)
- BFF -> API-Gateway mit serverseitigem `DASHBOARD_GATEWAY_AUTHORIZATION`
- API-Gateway -> interne Services mit `X-Gateway-Internal-Key` / `INTERNAL_API_KEY`

## Legacy / Dev

- Lokal kann Legacy-Admin (`GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN=true`) fuer Dev erlaubt sein.
- In Production muss Legacy-Admin deaktiviert bleiben.
- Demo-/Fake-Pfade sind immer als non-production dokumentiert und duerfen kein Live erlauben.

## Externe Auth-Schritte (operativ)

1. JWT fuer Dashboard BFF serverseitig setzen (`DASHBOARD_GATEWAY_AUTHORIZATION`).
2. Gateway-Secrets (`GATEWAY_JWT_SECRET`, optional `GATEWAY_INTERNAL_API_KEY`) sicher bereitstellen.
3. `GATEWAY_SUPER_ADMIN_SUBJECT` auf Philipps Subject setzen.
4. Produktionsstart nur mit `GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN=false`.
