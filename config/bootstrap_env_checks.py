"""
Fail-fast-Helfer fuer Startskripte und validate_env_profile.

Alle Meldungen: Deutsch, ohne stilles Wegfiltern.
"""

from __future__ import annotations

from urllib.parse import urlparse

from config.bootstrap_env_truth import DOCKER_COMPOSE_SERVICE_HOSTS
from config.settings import MIN_PRODUCTION_SECRET_LEN


def _parse_host(url: str) -> str:
    try:
        p = urlparse((url or "").strip())
        return (p.hostname or "").lower()
    except Exception:
        return ""


def url_host_is_loopback(url: str) -> bool:
    h = _parse_host(url)
    return h in ("localhost", "127.0.0.1", "::1", "[::1]")


def url_host_is_docker_compose_service(url: str) -> bool:
    return _parse_host(url) in DOCKER_COMPOSE_SERVICE_HOSTS


_WEAK_INTERNAL_KEYS: frozenset[str] = frozenset(
    {
        "changeme",
        "change_me",
        "internal",
        "secret",
        "test",
        "dev",
        "local",
    }
)


def bootstrap_env_consistency_issues(
    env: dict[str, str],
    *,
    profile: str,
) -> list[str]:
    """
    Zusaetzliche Regeln zu required_secrets_matrix: URL-Kontext, Schluesselstaerke.

    profile: local | staging | shadow | production (wie CLI).
    """
    issues: list[str] = []
    prod_like = profile in ("staging", "shadow", "production")

    def _truth(name: str) -> str:
        return (
            f"Siehe config/bootstrap_env_truth.py und docker-compose.yml "
            f"(Host vs. Container). Variable: {name}."
        )

    for name in ("API_GATEWAY_URL", "NEXT_PUBLIC_API_BASE_URL", "NEXT_PUBLIC_WS_BASE_URL"):
        raw = (env.get(name) or "").strip()
        if not raw:
            continue
        probe = raw.replace("ws://", "http://", 1).replace("wss://", "https://", 1)
        if url_host_is_docker_compose_service(probe):
            hint_port = "ws://127.0.0.1:8000" if name == "NEXT_PUBLIC_WS_BASE_URL" else "http://127.0.0.1:8000"
            issues.append(
                f"  {name}: Docker-Dienstname ({_parse_host(probe)!r}) im Host-/Browser-Kontext — nicht aufloesbar. "
                f"Vom Host erreichbare URL setzen (lokal typisch {hint_port}). "
                f"Im Dashboard-Container setzt Compose API_GATEWAY_URL=http://api-gateway:8000 automatisch. {_truth(name)}"
            )

    for key, val in sorted(env.items()):
        if not key.startswith("HEALTH_URL_"):
            continue
        v = (val or "").strip()
        if not v:
            continue
        if prod_like and url_host_is_loopback(v):
            issues.append(
                f"  {key}: localhost/127.0.0.1 in {profile!r} — "
                f"Worker laufen im Container-Netz; Health-URLs brauchen Dienstnamen "
                f"(z. B. http://market-stream:8010/ready), nicht Host-Loopback. {_truth(key)}"
            )

    rr = (env.get("READINESS_REQUIRE_URLS") or "").strip()
    if rr and prod_like:
        for part in rr.split(","):
            p = part.strip()
            if p and url_host_is_loopback(p):
                issues.append(
                    "  READINESS_REQUIRE_URLS: enthaelt localhost/127.0.0.1 — im Container falsch. "
                    f"Peer-URLs mit Docker-Hostnamen setzen. {_truth('READINESS_REQUIRE_URLS')}"
                )
                break

    llm_base = (env.get("LLM_ORCH_BASE_URL") or "").strip()
    if llm_base and prod_like and url_host_is_loopback(llm_base):
        issues.append(
            f"  LLM_ORCH_BASE_URL: localhost in {profile!r} — Gateway im Container erreicht den Orchestrator "
            f"nicht unter 127.0.0.1. Nutze z. B. http://llm-orchestrator:8070. {_truth('LLM_ORCH_BASE_URL')}"
        )

    for ds_key in ("DATABASE_URL_DOCKER", "REDIS_URL_DOCKER"):
        v = (env.get(ds_key) or "").strip()
        if not v:
            continue
        if "localhost" in v.lower() or "127.0.0.1" in v:
            issues.append(
                f"  {ds_key}: Host-Loopback — andere Container erreichen Postgres/Redis dort nicht. "
                f"Compose setzt typisch postgresql://...@postgres:5432/... und redis://redis:6379/0. {_truth(ds_key)}"
            )

    ik = (env.get("INTERNAL_API_KEY") or "").strip()
    if prod_like and ik and len(ik) < MIN_PRODUCTION_SECRET_LEN:
        issues.append(
            f"  INTERNAL_API_KEY: zu kurz (min. {MIN_PRODUCTION_SECRET_LEN} Zeichen in Shadow/Production/Staging). "
            "Schwache Keys fuehren zu leicht erratbarem Dienst-zu-Dienst-Zugang."
        )
    if prod_like and ik and ik.strip().lower() in _WEAK_INTERNAL_KEYS:
        issues.append(
            "  INTERNAL_API_KEY: offensichtlich schwacher Platzhalterwort-Wert — "
            "starken zufaelligen Wert setzen."
        )

    return issues
