"""
Sandbox: Tests nur unter kontrolliertem cwd (optional volle Repo-Kopie).

Vollstaendiger Gate-Lauf: ``tools/run_tests.sh`` im Repo-Root (siehe README im Paket).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from learning_engine.self_healing.protocol import SandboxTestResult

logger = logging.getLogger("learning_engine.self_healing.sandbox")


def default_sandbox_test_argv(work: Path) -> list[str]:
    custom = (os.environ.get("SELF_HEALING_TEST_CMD") or "").strip()
    if custom:
        return custom.split()
    if (work / "tests").is_dir():
        return [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/unit/test_self_healing_code_fix_agent.py",
            "--tb=no",
        ]
    le = work / "services" / "learning-engine" / "src" / "learning_engine"
    if le.is_dir():
        return [sys.executable, "-m", "compileall", "-q", str(le)]
    return [sys.executable, "-c", "print('self_heal:skip_tests'); raise SystemExit(0)"]


def run_tests_in_sandbox(
    repo_root: Path,
    *,
    timeout_sec: float = 420.0,
) -> SandboxTestResult:
    """
    Standard: Tests im Repo-Root (keine Kopie). Strikte Isolation optional via
    ``SELF_HEALING_FULL_REPO_COPY=1`` (temporaere Kopie, langsamer).
    """
    full_copy = os.environ.get("SELF_HEALING_FULL_REPO_COPY", "").lower() in (
        "1",
        "true",
        "yes",
    )
    tmp: tempfile.TemporaryDirectory[str] | None = None
    if full_copy:
        tmp = tempfile.TemporaryDirectory(prefix="apex_self_heal_")
        work = Path(tmp.name)
        shutil.copytree(
            repo_root,
            work,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "node_modules"),
        )
    else:
        work = repo_root

    cmd = default_sandbox_test_argv(work)
    env = os.environ.copy()
    sp = work / "shared" / "python" / "src"
    if sp.is_dir():
        pp = str(sp)
        env["PYTHONPATH"] = pp + os.pathsep + env.get("PYTHONPATH", "")
    env["SELF_HEALING_SANDBOX_ACTIVE"] = "1"
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(work),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        return SandboxTestResult(
            exit_code=int(proc.returncode),
            stdout_tail=(proc.stdout or "")[-12_000:],
            stderr_tail=(proc.stderr or "")[-12_000:],
            command_de=" ".join(cmd),
        )
    except subprocess.TimeoutExpired as exc:
        return SandboxTestResult(
            exit_code=124,
            stdout_tail=(exc.stdout or "")[-12_000:] if exc.stdout else "",
            stderr_tail=(exc.stderr or "")[-12_000:] if exc.stderr else "timeout",
            command_de=" ".join(cmd),
        )
    finally:
        if tmp is not None:
            tmp.cleanup()
