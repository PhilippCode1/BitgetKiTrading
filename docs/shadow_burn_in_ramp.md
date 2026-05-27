# Shadow-Burn-in Ramp (Ops)

Dieses Dokument beschreibt den **pflichtigen Shadow-Burn-in** vor LIVE-Trading mit
Kundengeld. Es ersetzt kein signiertes Zertifikat — es ist die **Repo-seitige
Betriebsanleitung** und Verweis auf die automatisierten Prüfer.

## Ziel

Mindestens **72 Stunden** (empfohlen: **14 Kalendertage**) unter:

- `EXECUTION_MODE=shadow`
- `LIVE_TRADE_ENABLE=false`
- `SHADOW_TRADE_ENABLE=true`
- `REQUIRE_SHADOW_MATCH_BEFORE_LIVE=true`
- `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true`

…ohne P0-Vorfälle, ohne chronische Reconcile-Fails, ohne Shadow/Live-Divergenz.

## Ablauf

### 1. Stack starten (Production-Profil, Shadow-Modus)

```powershell
pwsh scripts/start_production.ps1
```

Vor dem ersten Start:

```powershell
pnpm env:10-10:production
pnpm go-live:preflight:strict   # echte .env.production
```

### 2. Burn-in laufen lassen

- Mandant in Shadow mit echten Marktdaten, **ohne** Exchange-Submits
- Operator-Release-Gates aktiv lassen
- Alerts und Reconcile beobachten

### 3. Evidenz erzeugen (DB-gestützt)

```powershell
python scripts/verify_shadow_burn_in.py --env-file .env.production --hours 72 --strict
```

Ausgabe: `READINESS_EVIDENCE.md` + optional `--output-json`.

### 4. Externes Zertifikat (L4+)

Nach erfolgreichem DB-Burn-in:

```powershell
python scripts/verify_shadow_burn_in.py --write-certificate-template reports/shadow_certificate.template.json
# Nach externer Review ausfüllen, dann:
python scripts/verify_shadow_burn_in.py --certificate-json reports/shadow_certificate.json --strict
```

Archivieren unter `docs/release_evidence/` mit Marker-Zeile (siehe
`docs/release_evidence/README.md`).

## Go-Live danach (Portal)

1. Vertrag + Modul-Mate-Gates in DB (`admin_review_complete`)
2. `POST /v1/commerce/customer/live-execution/enable` (Step-Up, Bitget-Ping, E-Mail)
3. `GO_LIVE_COOLDOWN_SEC` abwarten
4. Vault: `bitget/{tenant_id}/live` befüllen
5. Erst dann `LIVE_TRADE_ENABLE=true` (Operator-Freigabe, nicht autonom)

## Verifikation im Repo

| Prüfung | Befehl |
|---|---|
| ENV 10/10 | `pnpm env:10-10:production` |
| Go-Live Ops | `pnpm go-live:preflight` |
| Burn-in (DB) | `python scripts/verify_shadow_burn_in.py --strict` |
| Readiness-Audit | `python tools/production_readiness_audit.py` |

## No-Go

- Ein Rot in `verify_shadow_burn_in.py --strict`
- `GATEWAY_MOCK_BITGET_VERIFY=true` in Production
- LIVE ohne Vault-Tenant-Credentials (`TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT=true`)
- Mock-Login (`PORTAL_AUTH_PROVIDER=mock`) in Production
