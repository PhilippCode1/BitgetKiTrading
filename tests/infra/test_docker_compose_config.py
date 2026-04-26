"""Optional: docker compose config --quiet muss fuer die Stack-Datei parsen (ohne Start)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

_has_docker = shutil.which("docker") is not None

skip_no_docker = pytest.mark.skipif(
    not _has_docker,
    reason="Docker-CLI nicht auf PATH (lokal/CI ohne Engine: Test uebersprungen)",
)


@skip_no_docker
def test_docker_compose_config_quiet_parses() -> None:
    r = subprocess.run(
        ["docker", "compose", "config", "--quiet"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)


@skip_no_docker
def test_docker_compose_merged_with_local_publish_parses_like_ci() -> None:
    """Gleicher Merge wie Job compose_healthcheck in .github/workflows/ci.yml."""
    r = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.yml",
            "-f",
            "docker-compose.local-publish.yml",
            "config",
            "--quiet",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
