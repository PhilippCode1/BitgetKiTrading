#!/usr/bin/env bash
# Postgres-Backup ueber laufenden Compose-Container (Single-Host Production).
# Keine Secrets in stdout/stderr — Passwort nur per Container-ENV.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${COMPOSE_ENV_FILE:-.env.production}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-}"

COMPOSE_FILES=(-f docker-compose.yml)
if [[ -f docker-compose.production-ops.yml ]]; then
  COMPOSE_FILES+=(-f docker-compose.production-ops.yml)
fi

load_env_file() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    echo "FEHLER: Env-Datei fehlt: $file" >&2
    exit 1
  fi
  while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
    local line="${raw_line%$'\r'}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    [[ "$line" != *=* ]] && continue
    export "$line"
  done < "$file"
}

load_env_file "$ENV_FILE"

POSTGRES_DB="${POSTGRES_DB:-bitget_ai}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"

compose() {
  COMPOSE_ENV_FILE="$ENV_FILE" \
  docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" "$@"
}

if ! compose ps --status running -q postgres 2>/dev/null | grep -q .; then
  echo "FEHLER: Postgres-Container laeuft nicht. Start: bash scripts/start_production.sh" >&2
  exit 1
fi

if ! compose exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
  echo "FEHLER: Postgres antwortet nicht auf pg_isready (User=$POSTGRES_USER DB=$POSTGRES_DB)." >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
outfile="${BACKUP_DIR}/postgres_${POSTGRES_DB}_${ts}.sql.gz"

echo "==> Backup: $outfile (DB=$POSTGRES_DB User=$POSTGRES_USER)"

compose exec -T postgres pg_dump \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --no-owner \
  --no-acl \
  | gzip -c >"$outfile"

if [[ ! -s "$outfile" ]]; then
  echo "FEHLER: Backup-Datei ist leer." >&2
  exit 1
fi

size="$(wc -c <"$outfile" | tr -d ' ')"
echo "OK  Backup geschrieben ($size bytes, komprimiert)"

if [[ -n "$BACKUP_RETENTION_DAYS" && "$BACKUP_RETENTION_DAYS" =~ ^[0-9]+$ ]]; then
  deleted="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'postgres_*.sql.gz' -mtime +"$BACKUP_RETENTION_DAYS" -print -delete | wc -l | tr -d ' ')"
  echo "==> Retention: BACKUP_RETENTION_DAYS=$BACKUP_RETENTION_DAYS — entfernt: $deleted Datei(en)"
fi
