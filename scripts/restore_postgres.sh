#!/usr/bin/env bash
# Postgres-Restore aus Backup (Compose-Container). Destruktiv — Bestaetigung erforderlich.
# Keine Secrets in stdout/stderr.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup.sql|backup.sql.gz>" >&2
  echo "  COMPOSE_ENV_FILE=.env.production $0 ./backups/postgres_bitget_ai_YYYYMMDD.sql.gz" >&2
  exit 1
fi

BACKUP_PATH="$1"
ENV_FILE="${COMPOSE_ENV_FILE:-.env.production}"

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

if [[ ! -f "$BACKUP_PATH" ]]; then
  echo "FEHLER: Backup-Datei nicht gefunden: $BACKUP_PATH" >&2
  exit 1
fi

compose() {
  COMPOSE_ENV_FILE="$ENV_FILE" \
  docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" "$@"
}

if ! compose ps --status running -q postgres 2>/dev/null | grep -q .; then
  echo "FEHLER: Postgres-Container laeuft nicht." >&2
  exit 1
fi

echo "================================================================"
echo " WARNUNG: Postgres-Restore ueberschreibt Daten in DB=$POSTGRES_DB"
echo " Backup: $BACKUP_PATH"
echo " Stoppe vorher App-Container (live-broker, api-gateway, …), wenn moeglich."
echo "================================================================"
printf "Zum Fortfahren exakt RESTORE eingeben: "
read -r confirm
if [[ "$confirm" != "RESTORE" ]]; then
  echo "Abgebrochen (Eingabe war nicht RESTORE)."
  exit 1
fi

echo "==> Restore startet (User=$POSTGRES_USER DB=$POSTGRES_DB)"

restore_stream() {
  if [[ "$BACKUP_PATH" == *.gz ]]; then
    gunzip -c "$BACKUP_PATH"
  else
    cat "$BACKUP_PATH"
  fi
}

restore_stream | compose exec -T postgres psql \
  -v ON_ERROR_STOP=1 \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB"

echo "OK  Restore abgeschlossen. App-Stack neu starten und Healthchecks ausfuehren."
