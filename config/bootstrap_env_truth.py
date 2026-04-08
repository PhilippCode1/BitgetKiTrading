"""
Source of Truth: welche URLs in welchem Kontext gelten.

Host-Kontext (Skripte auf dem Rechner, `pnpm dev` fuer Next auf dem Host):
  - API_GATEWAY_URL, APP_BASE_URL, Healthchecks: vom Host aus erreichbar, typisch
    http://127.0.0.1:8000 (nicht Docker-Dienstnamen).

Container-Kontext (docker-compose.yml, Engine-zu-Engine):
  - DATABASE_URL / REDIS_URL in App-Containern: fest im Compose-Anker
    `x-app-runtime-env` auf postgres:/redis: (nicht Host-localhost).
  - api-gateway HEALTH_URL_*: im Standard-Compose literal auf
    http://<dienstname>:<port>/ready gesetzt (ueberschreibt .env.local-Zeilen).
  - dashboard API_GATEWAY_URL: im Compose auf http://api-gateway:8000 gesetzt.

Wenn BITGET_USE_DOCKER_DATASTORE_DSN=true (alle Pipeline-Container): Peer-URLs
duerfen nicht auf 127.0.0.1/localhost zeigen — das waere der Container selbst, nicht der Worker.
"""

from __future__ import annotations

# Bekannte Compose-Service-Hostnamen (kurzname). Nicht in Host-.env fuer API_GATEWAY_URL / NEXT_PUBLIC_*.
DOCKER_COMPOSE_SERVICE_HOSTS: frozenset[str] = frozenset(
    {
        "api-gateway",
        "market-stream",
        "feature-engine",
        "structure-engine",
        "drawing-engine",
        "signal-engine",
        "news-engine",
        "llm-orchestrator",
        "paper-broker",
        "learning-engine",
        "alert-engine",
        "monitor-engine",
        "live-broker",
        "postgres",
        "redis",
    }
)

HOST_EDGE_GATEWAY_HINT = "http://127.0.0.1:8000"
HOST_EDGE_DASHBOARD_HINT = "http://127.0.0.1:3000"
