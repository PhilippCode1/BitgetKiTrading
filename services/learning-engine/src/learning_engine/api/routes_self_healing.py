"""Interne Self-Healing-Apply-Route (Operator-Freigabe, Docker optional)."""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from redis import Redis

from learning_engine.config import LearningEngineSettings
from shared_py.service_auth import (
    InternalServiceAuthContext,
    build_internal_service_dependency,
)

logger = logging.getLogger("learning_engine.api.self_healing")


class SelfHealingApplyBody(BaseModel):
    proposal_id: str = Field(..., min_length=8, max_length=64)
    apply_token: str = Field(..., min_length=8, max_length=200)
    confirm: bool = Field(default=False, description="Muss true sein.")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _paths_from_diff(patch: str) -> list[str]:
    out: list[str] = []
    for line in patch.splitlines():
        m = re.match(r"^\+\+\+ b/(.+)$", line.strip())
        if m:
            out.append(m.group(1).strip())
    return list(dict.fromkeys(out))


def _allowed_prefixes(settings: LearningEngineSettings) -> tuple[str, ...]:
    raw = (settings.self_healing_apply_path_prefixes or "").strip()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return tuple(parts) if parts else ("services/", "shared/python/")


def _path_allowed(rel: str, prefixes: tuple[str, ...]) -> bool:
    rel = rel.replace("\\", "/")
    return any(rel.startswith(p) or rel.startswith("./" + p) for p in prefixes)


def build_self_healing_router(settings: LearningEngineSettings) -> APIRouter:
    r = APIRouter(tags=["self-healing"])
    require_internal = build_internal_service_dependency(settings)

    @r.post("/internal/self-healing/apply")
    def apply_self_healing_patch(
        body: SelfHealingApplyBody,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict[str, Any]:
        if not settings.self_healing_apply_enabled:
            raise HTTPException(
                status_code=403,
                detail={"code": "SELF_HEALING_APPLY_DISABLED", "message": "SELF_HEALING_APPLY_ENABLED=false"},
            )
        if not body.confirm:
            raise HTTPException(status_code=400, detail="confirm muss true sein")
        rcli = Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=5)
        try:
            tok = rcli.get(f"self_healing:apply:{body.proposal_id}")
            patch = rcli.get(f"self_healing:patch:{body.proposal_id}")
        finally:
            rcli.close()
        if not tok or not patch:
            raise HTTPException(status_code=404, detail="proposal abgelaufen oder unbekannt")
        if tok.strip() != body.apply_token.strip():
            raise HTTPException(status_code=403, detail="apply_token ungueltig")
        prefixes = _allowed_prefixes(settings)
        for p in _paths_from_diff(patch):
            if not _path_allowed(p, prefixes):
                raise HTTPException(
                    status_code=400,
                    detail={"code": "PATH_NOT_ALLOWED", "path": p, "prefixes": list(prefixes)},
                )
        repo = _repo_root()
        if not (repo / ".git").is_dir():
            raise HTTPException(
                status_code=503,
                detail="Kein Git-Repo im Container — git apply nicht moeglich",
            )
        patch_path = repo / f".self_healing_{body.proposal_id}.patch"
        patch_path.write_text(patch, encoding="utf-8")
        try:
            proc = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", str(patch_path)],
                cwd=str(repo),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if proc.returncode != 0:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "GIT_APPLY_FAILED",
                        "stderr": (proc.stderr or "")[:4000],
                        "stdout": (proc.stdout or "")[:2000],
                    },
                )
        finally:
            try:
                patch_path.unlink(missing_ok=True)
            except OSError:
                pass

        restart_out: str | None = None
        svc = (settings.self_healing_docker_restart or "").strip()
        if svc and os.environ.get("SELF_HEALING_DOCKER_CLI", "").lower() in ("1", "true", "yes"):
            try:
                dr = subprocess.run(
                    ["docker", "compose", "restart", svc],
                    cwd=str(repo),
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                restart_out = (dr.stdout or "")[:2000] + (dr.stderr or "")[:2000]
            except Exception as exc:
                restart_out = f"docker_restart_error:{exc}"[:2000]

        try:
            rcli = Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=5)
            rcli.delete(f"self_healing:apply:{body.proposal_id}")
            rcli.delete(f"self_healing:patch:{body.proposal_id}")
        finally:
            rcli.close()

        logger.warning(
            "self_healing APPLY ausgefuehrt proposal_id=%s (Operator-Freigabe)",
            body.proposal_id,
        )
        return {"ok": True, "applied": True, "docker_restart": restart_out}

    return r
