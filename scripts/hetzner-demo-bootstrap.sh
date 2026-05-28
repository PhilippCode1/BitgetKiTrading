#!/usr/bin/env bash
# Hetzner Demo-Stack Bootstrap (fail-closed, kein Live-Trading)
# Auf dem Server als root ausfuehren, z. B.:
#   curl -fsSL https://raw.githubusercontent.com/PhilippCode1/BitgetKiTrading/main/scripts/hetzner-demo-bootstrap.sh | bash
# oder nach git clone:
#   bash /opt/BitgetKiTrading/scripts/hetzner-demo-bootstrap.sh
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/BitgetKiTrading}"
REPO_URL="${REPO_URL:-https://github.com/PhilippCode1/BitgetKiTrading.git}"
SERVER_IPV4="${SERVER_IPV4:-}"
ENV_FILE="${ENV_FILE:-.env.demo}"
SYSTEMD_UNIT="${SYSTEMD_UNIT:-bitget-kit.service}"

log() { printf '[hetzner-demo] %s\n' "$*"; }
die() { printf '[hetzner-demo] FEHLER: %s\n' "$*" >&2; exit 1; }

require_root() {
  [[ "$(id -u)" -eq 0 ]] || die "Bitte als root ausfuehren."
}

detect_server_ip() {
  if [[ -n "$SERVER_IPV4" ]]; then
    return
  fi
  SERVER_IPV4="$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || true)"
  if [[ -z "$SERVER_IPV4" ]]; then
    SERVER_IPV4="$(hostname -I 2>/dev/null | awk '{print $1}')"
  fi
  [[ -n "$SERVER_IPV4" ]] || die "SERVER_IPV4 nicht ermittelbar — export SERVER_IPV4=178.105.246.97 setzen."
}

set_env_kv() {
  local file="$1" key="$2" value="$3"
  if grep -qE "^${key}=" "$file" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$file"
  else
    printf '\n%s=%s\n' "$key" "$value" >>"$file"
  fi
}

ensure_demo_safety() {
  local f="$1"
  set_env_kv "$f" LIVE_TRADE_ENABLE false
  set_env_kv "$f" SHADOW_TRADE_ENABLE false
  set_env_kv "$f" PRODUCTION false
  set_env_kv "$f" DEBUG false
  set_env_kv "$f" LOG_LEVEL INFO
  set_env_kv "$f" EXECUTION_MODE bitget_demo
  set_env_kv "$f" DEMO_ORDER_SUBMIT_ENABLE false
  set_env_kv "$f" BITGET_USE_DOCKER_DATASTORE_DSN true
  set_env_kv "$f" COMPOSE_ENV_FILE .env.demo
  set_env_kv "$f" COMPOSE_EDGE_BIND 0.0.0.0
}

generate_internal_secrets() {
  local f="$1"
  local keys=(
    INTERNAL_API_KEY
    SERVICE_INTERNAL_API_KEY
    GATEWAY_INTERNAL_API_KEY
    JWT_SECRET
    GATEWAY_JWT_SECRET
    SECRET_KEY
    ENCRYPTION_KEY
    ADMIN_TOKEN
  )
  for key in "${keys[@]}"; do
    if grep -qE "^${key}=.*<SET_ME" "$f" 2>/dev/null || grep -qE "^${key}=$" "$f" 2>/dev/null; then
      set_env_kv "$f" "$key" "$(openssl rand -hex 32)"
      log "Synthetisches Secret gesetzt: $key (nur lokal auf dem Server)"
    fi
  done
}

patch_public_urls() {
  local f="$1" ip="$2"
  set_env_kv "$f" APP_BASE_URL "http://${ip}:8000"
  set_env_kv "$f" API_GATEWAY_URL "http://${ip}:8000"
  set_env_kv "$f" DASHBOARD_URL "http://${ip}:3000"
  set_env_kv "$f" FRONTEND_URL "http://${ip}:3000"
  set_env_kv "$f" CORS_ALLOW_ORIGINS "http://${ip}:3000"
  set_env_kv "$f" NEXT_PUBLIC_API_BASE_URL "http://${ip}:8000"
  set_env_kv "$f" NEXT_PUBLIC_WS_BASE_URL "ws://${ip}:8000"
}

install_packages() {
  log "System aktualisieren …"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get upgrade -y -qq
  apt-get install -y -qq git curl ca-certificates nano htop ufw openssl
}

install_docker() {
  if command -v docker >/dev/null 2>&1; then
    log "Docker bereits installiert: $(docker --version)"
  else
    log "Docker installieren …"
    curl -fsSL https://get.docker.com | sh
  fi
  apt-get install -y -qq docker-compose-plugin
  docker --version
  docker compose version
}

clone_repo() {
  log "Pruefe /opt …"
  ls -la /opt
  if [[ -d "$REPO_DIR/.git" ]]; then
    log "Repo existiert bereits: $REPO_DIR — kein Loeschen, git pull"
    git -C "$REPO_DIR" pull --ff-only
  else
    log "Klone Repository nach $REPO_DIR …"
    git clone "$REPO_URL" "$REPO_DIR"
  fi
}

prepare_env_demo() {
  local f="$REPO_DIR/$ENV_FILE"
  cd "$REPO_DIR"
  for want in docker-compose.yml .env.demo.example; do
    [[ -f "$want" ]] || die "Fehlt im Repo: $want"
  done
  if [[ ! -f "$ENV_FILE" ]]; then
    cp .env.demo.example "$ENV_FILE"
    log "$ENV_FILE aus .env.demo.example erstellt"
  else
    log "$ENV_FILE existiert bereits — wird nur sicher ergaenzt"
  fi
  ensure_demo_safety "$f"
  generate_internal_secrets "$f"
  patch_public_urls "$f" "$SERVER_IPV4"
  if grep -qE 'BITGET_DEMO_API_KEY=.*<SET_ME' "$f"; then
    log "WARNUNG: BITGET_DEMO_API_* noch Platzhalter — Stack kann starten, Bitget-Demo-Verbindung braucht deine Keys lokal in $f"
  fi
}

configure_ufw() {
  if ! command -v ufw >/dev/null 2>&1; then
    return
  fi
  log "UFW vorsichtig konfigurieren (OpenSSH zuerst) …"
  ufw allow OpenSSH || true
  ufw allow 22/tcp || true
  ufw allow 3000/tcp || true
  ufw allow 8000/tcp || true
  ufw allow 80/tcp || true
  ufw allow 443/tcp || true
  if ufw status | grep -q 'Status: active'; then
    log "UFW bereits aktiv"
  else
    ufw --force enable
    log "UFW aktiviert"
  fi
}

start_compose() {
  cd "$REPO_DIR"
  log "Docker Compose Demo-Stack starten (kann mehrere Minuten dauern) …"
  docker compose --env-file "$ENV_FILE" up --build -d
  docker compose --env-file "$ENV_FILE" ps
}

install_systemd() {
  cat >"/etc/systemd/system/${SYSTEMD_UNIT}" <<UNIT
[Unit]
Description=BitgetKiTrading Docker Compose Stack (Demo)
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${REPO_DIR}
RemainAfterExit=yes
ExecStart=/usr/bin/docker compose --env-file ${ENV_FILE} up -d --build
ExecStop=/usr/bin/docker compose --env-file ${ENV_FILE} down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable "${SYSTEMD_UNIT%.service}"
  systemctl restart "${SYSTEMD_UNIT%.service}" || systemctl start "${SYSTEMD_UNIT%.service}"
  systemctl status "${SYSTEMD_UNIT%.service}" --no-pager || true
}

print_summary() {
  cd "$REPO_DIR"
  log "=== Zusammenfassung ==="
  log "Dashboard: http://${SERVER_IPV4}:3000"
  log "API:       http://${SERVER_IPV4}:8000"
  log "LIVE_TRADE_ENABLE muss false bleiben."
  ss -tulpn | grep -E '3000|8000' || log "Ports 3000/8000 noch nicht sichtbar — Container evtl. noch im Build"
  docker compose --env-file "$ENV_FILE" logs --tail=80 || true
}

main() {
  require_root
  detect_server_ip
  log "Server-IP: $SERVER_IPV4"
  install_packages
  install_docker
  clone_repo
  prepare_env_demo
  configure_ufw
  start_compose
  install_systemd
  print_summary
}

main "$@"
