# Google Compute Engine — Single-Host mit Docker Compose

Diese Anleitung beschreibt den Production-Betrieb des Stacks auf einer **Ubuntu 24.04** VM in **Google Compute Engine (GCE)**:

- Docker Compose als Laufzeit
- **Nur** HTTP/HTTPS (80/443) öffentlich — Reverse Proxy vor dem Stack
- API-Gateway (`8000`) und Dashboard (`3000`) nur auf **Loopback** (`127.0.0.1`)
- Interne Services (Engines, Broker, Postgres, Redis) **ohne** öffentliche Ports

Trading-Logik und Live-Gates werden hier nicht geändert; Start erfolgt typisch mit `EXECUTION_MODE=shadow` bis zum operativen Go-Live.

---

## 1. VM anlegen (GCE)

| Empfehlung | Wert |
|------------|------|
| OS | Ubuntu 24.04 LTS |
| Maschinentyp | min. `e2-standard-4` (Full-Stack-Build braucht RAM) |
| Boot-Disk | ≥ 100 GB SSD |
| Netzwerk-Tags | z. B. `bitget-http-server` für Firewall-Regeln |

**Firewall (GCP):** nur eingehend **TCP 22** (SSH, eingeschränkt auf Admin-IPs), **80**, **443**.  
**Nicht** öffnen: `3000`, `8000`, `5432`, `6379`, `9090`, Engine-Ports.

Optional auf der VM: `ufw` mit gleicher Policy (`allow 22,80,443`).

---

## 2. Docker installieren

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
# Optional: ShellCheck fuer Bash-Skripte (Backup/Restore/Bootstrap)
sudo apt-get install -y shellcheck
sudo usermod -aG docker "$USER"
# Neu einloggen, dann: docker compose version
# shellcheck scripts/backup_postgres.sh scripts/restore_postgres.sh scripts/bootstrap_stack.sh
```

---

## 3. Repository klonen

```bash
sudo mkdir -p /opt/bitget-btc-ai
sudo chown "$USER:$USER" /opt/bitget-btc-ai
git clone https://github.com/<ORG>/bitget-btc-ai.git /opt/bitget-btc-ai
cd /opt/bitget-btc-ai
```

---

## 4. Production-ENV (nicht committen)

```bash
cp .env.production.example .env.production
chmod 600 .env.production
# Alle YOUR_* / <SET_*> Platzhalter ersetzen (Secrets aus Vault/Secret Manager — nicht ins Git).
```

Wichtige Keys (Auszug):

| Variable | Hinweis |
|----------|---------|
| `COMPOSE_ENV_FILE` | `.env.production` (in Example gesetzt) |
| `COMPOSE_EDGE_BIND` | `127.0.0.1` |
| `DATABASE_URL_DOCKER` | `...@postgres:5432/...` (Container-Netz) |
| `DATABASE_URL` | Host-DSN nur bei Ops-Overlay: `...@127.0.0.1:5432/...` |
| `APP_BASE_URL` / `FRONTEND_URL` / `NEXT_PUBLIC_*` | Öffentliche HTTPS/WSS-URLs |
| `DASHBOARD_GATEWAY_AUTHORIZATION` | `Bearer …` (z. B. via `scripts/mint_dashboard_gateway_jwt.py`) |

```bash
export COMPOSE_ENV_FILE=.env.production
```

---

## 5. Preflight und Validierung

```bash
cd /opt/bitget-btc-ai
export COMPOSE_ENV_FILE=.env.production

python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt   # fuer validate/preflight

python tools/compose_start_preflight.py --env-file .env.production --profile production
python tools/validate_env_profile.py --env-file .env.production --profile production
bash scripts/go_live_check.sh .env.production
```

---

## 6. Stack starten

**Empfohlen** (gestaffelt, Production-Migration über Compose-Service `migrate`):

```bash
export COMPOSE_ENV_FILE=.env.production
bash scripts/start_production.sh
# intern: bootstrap_stack.sh production
# merged: docker-compose.yml + docker-compose.production-ops.yml
```

Optionen:

```bash
bash scripts/bootstrap_stack.sh production --no-build          # Images bereits gebaut
bash scripts/bootstrap_stack.sh production --skip-migrations # migrate manuell
bash scripts/bootstrap_stack.sh production --with-observability
```

**Manuell** (nicht empfohlen ohne Preflight):

```bash
export COMPOSE_ENV_FILE=.env.production
docker compose -f docker-compose.yml -f docker-compose.production-ops.yml \
  --env-file .env.production up -d --build
```

`docker-compose.production-ops.yml` published Postgres/Redis **nur** auf `127.0.0.1` — für Backups und Host-Tools, nicht für das Internet.

---

## 7. Healthchecks

Nach Bootstrap:

```bash
export COMPOSE_ENV_FILE=.env.production
# URLs aus .env.production laden (HTTPS fuer Edge)
set -a && source .env.production && set +a
export HEALTHCHECK_EDGE_ONLY=true
bash scripts/healthcheck.sh
```

Einzelchecks:

- API: `curl -fsS "$API_GATEWAY_URL/ready"`
- Dashboard: `curl -fsS "$DASHBOARD_URL/api/health"`
- Aggregat: `curl -fsS "$API_GATEWAY_URL/v1/system/health"`

---

## 8. Reverse Proxy und HTTPS

Vorlage: `infra/reverse-proxy/nginx.single-host.conf`

1. Domains und Zertifikatspfade anpassen (`api.example.com`, `dashboard.example.com`).
2. nginx auf der VM installieren; Site nach `/etc/nginx/sites-enabled/` verlinken.
3. Let’s Encrypt (certbot) für TLS.
4. Upstreams zeigen auf **Loopback**:
   - API → `127.0.0.1:8000`
   - Dashboard → `127.0.0.1:3000`
5. In `.env.production`: `GATEWAY_SEND_HSTS=true`, `GATEWAY_SSE_COOKIE_SECURE=true`.

Öffentlich erreichbar sind nur **80/443** am nginx — nicht die Compose-Edge-Ports direkt.

---

## 9. Backup und Restore

### Backup (täglich per Cron)

```bash
export COMPOSE_ENV_FILE=.env.production
export BACKUP_DIR=/var/backups/bitget-btc-ai
export BACKUP_RETENTION_DAYS=14
bash scripts/backup_postgres.sh
```

Cron-Beispiel (`crontab -e`):

```cron
0 3 * * * cd /opt/bitget-btc-ai && COMPOSE_ENV_FILE=.env.production BACKUP_DIR=/var/backups/bitget-btc-ai BACKUP_RETENTION_DAYS=14 bash scripts/backup_postgres.sh >> /var/log/bitget-pg-backup.log 2>&1
```

Zusätzlich: GCE-Disk-Snapshots für das Docker-Volume `pgdata`.

### Restore (destruktiv)

```bash
# App-Last reduzieren: docker compose stop api-gateway live-broker ...
export COMPOSE_ENV_FILE=.env.production
bash scripts/restore_postgres.sh /var/backups/bitget-btc-ai/postgres_bitget_ai_YYYYMMDD.sql.gz
# Eingabe: RESTORE
bash scripts/start_production.sh
```

Drill/Evidence (optional): `python tools/dr_postgres_restore_drill.py`

---

## 10. Sicherheits-Checkliste

- [ ] `.env.production` Rechte `600`, nicht in Git
- [ ] `COMPOSE_EDGE_BIND=127.0.0.1`
- [ ] GCP-Firewall: kein 3000/8000/5432 von `0.0.0.0/0`
- [ ] `EXECUTION_MODE=shadow`, `LIVE_TRADE_ENABLE=false` bis Go-Live
- [ ] Vault/Secret-Store für Exchange- und API-Keys
- [ ] Regelmäßige Backups + Restore-Drill

---

## Referenzen

| Thema | Datei |
|-------|--------|
| Compose-Basis | `docker-compose.yml` |
| Ops-Overlay (Loopback DB) | `docker-compose.production-ops.yml` |
| Bootstrap | `scripts/bootstrap_stack.sh`, `scripts/start_production.sh` |
| ENV-Vorlage | `.env.production.example` |
| Infrastruktur | `docs/deployment/INFRASTRUCTURE_AND_ENV.md` |
| Operator | `docs/runbooks/OPERATOR_MANUAL.md` |
