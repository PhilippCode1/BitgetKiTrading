# GitHub Branch Protection (main)

`gh` CLI ist lokal nicht verfuegbar, daher muss die Branch-Protection in GitHub manuell gesetzt werden.

## Ziel

`main` soll nur per Pull Request mit gruener CI gemerged werden.

## Schritt-fuer-Schritt

1. GitHub Repo oeffnen: `PhilippCode1/BitgetKiTrading`
2. `Settings`
3. `Branches`
4. `Add branch protection rule` fuer Branch-Pattern `main`
5. `Require a pull request before merging` aktivieren
6. `Require status checks to pass before merging` aktivieren
7. `Require branches to be up to date before merging` aktivieren
8. Unter `Status checks that are required` mindestens auswaehlen:
   - `release-approval-gate`
   - `demo-env-compose-safety`
9. Optional zusaetzlich die Upstream-Jobs als Required setzen:
   - `python`
   - `dashboard`
   - `compose_healthcheck`
10. `Block force pushes` aktivieren
11. `Block deletions` aktivieren
12. Regel speichern

## Exakte CI-Namen aus `.github/workflows/ci.yml`

- Workflow-Name: `ci`
- Job-Namen:
  - `python`
  - `demo-env-compose-safety`
  - `dashboard`
  - `compose_healthcheck`
  - `release-approval-gate`

Empfehlung fuer Required Checks:

- Pflicht: `release-approval-gate`
- Zusaetzlich (defensiv): `demo-env-compose-safety`
