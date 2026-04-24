from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("monitor_engine.self_healing.restarter")


@dataclass(frozen=True)
class ServiceRestarter:
    """
    `mock`: kein echter Prozess (lokale Tests, CI).
    `docker`: Docker Engine API 1.24+ via Unix-Sock oder TCP
      (``DOCKER_HOST=unix:///var/run/docker.sock``) — nur wenn Containername konfigurierbar.
    `compose_exec`: `docker compose restart <svc>` (optional, hinter ``MONITOR_SH_COMPOSE``).
    """

    mode: str
    """mock | docker | compose_exec"""
    label_to_docker_id: str | None = None
    """
    Trunkierte ENV-Zeile ``name=dockername,name2=...`` bzw. JSON, um feature-engine
    -> Compose-Service zu mappen. Leer = `service_name` 1:1.
    """

    @classmethod
    def from_settings(cls, settings: Any) -> "ServiceRestarter":
        m = (getattr(settings, "monitor_self_healing_restarter_mode", "mock") or "mock").strip()
        m = m.lower() if m else "mock"
        mraw = (getattr(settings, "monitor_self_healing_docker_name_map", "") or "").strip()
        return cls(mode=m, label_to_docker_id=mraw or None)

    def _map_name(self, service_name: str) -> str:
        if not self.label_to_docker_id:
            return service_name
        s = self.label_to_docker_id
        for part in s.split(","):
            part = part.strip()
            if not part or "=" not in part:
                continue
            a, b = part.split("=", 1)
            if a.strip() == service_name:
                return b.strip() or service_name
        return service_name

    def restart(self, service_name: str) -> dict[str, Any]:
        m = (self.mode or "mock").lower()
        dname = self._map_name(service_name)
        if m in ("0", "false", "mock", "dry_run", "dryrun"):
            logger.info("self-healing restarter (mock) service_name=%r docker=%r", service_name, dname)
            return {
                "ok": True,
                "mode": "mock",
                "container_name": f"{dname} (simuliert)",
                "service_name": service_name,
            }
        if m in ("docker", "docker_api"):
            return _restart_docker_cli(dname, service_name)
        if m in ("compose", "compose_exec", "docker_compose"):
            return _restart_compose(dname, service_name)
        logger.warning("unbekannte self-healing restarter mode=%r — fallback mock", m)
        return {
            "ok": True,
            "mode": "unknown_fallback_mock",
            "container_name": dname,
            "service_name": service_name,
        }


def _restart_docker_cli(dname: str, service_name: str) -> dict[str, Any]:
    try:
        cp = subprocess.run(  # noqa: S603
            ["docker", "restart", dname],
            capture_output=True,
            text=True,
            timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("docker restart fehlgeschlagen %s: %s", dname, exc)
        return {
            "ok": False,
            "mode": "docker",
            "error": str(exc)[:200],
            "service_name": service_name,
        }
    if cp.returncode != 0:
        return {
            "ok": False,
            "mode": "docker",
            "stderr": (cp.stderr or cp.stdout)[:500],
            "service_name": service_name,
        }
    return {"ok": True, "mode": "docker", "container": dname, "service_name": service_name}


def _restart_compose(dname: str, service_name: str) -> dict[str, Any]:
    cdir = (os.environ.get("MONITOR_SH_COMPOSE_CWD", "") or "").strip()
    ffile = (os.environ.get("MONITOR_SH_COMPOSE_FILE", "docker-compose.yml") or "docker-compose.yml").strip()
    if not cdir or not os.path.isdir(cdir):
        logger.info("MONITOR_SH_COMPOSE_CWD nicht gesetzt — compose_exec uebersprungen (mock)")
        return {
            "ok": True,
            "mode": "compose_exec_skipped_no_cwd",
            "service_name": service_name,
            "compose_target": dname,
        }
    try:
        cp = subprocess.run(  # noqa: S603
            ["docker", "compose", "-f", ffile, "restart", dname],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=cdir,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "mode": "compose_exec", "error": str(exc)[:200], "service_name": service_name}
    if cp.returncode != 0:
        return {
            "ok": False,
            "mode": "compose_exec",
            "stderr": (cp.stderr or cp.stdout)[:500],
            "service_name": service_name,
        }
    return {
        "ok": True,
        "mode": "compose_exec",
        "compose_target": dname,
        "service_name": service_name,
    }
