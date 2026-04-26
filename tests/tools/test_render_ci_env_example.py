from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_render_ci_env_example_replaces_set_me(tmp_path: Path) -> None:
    src = tmp_path / "in.env"
    dst = tmp_path / "out.env"
    src.write_text("A=<SET_ME>\nB=ok\n", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "tools/render_ci_env_example.py",
            "--input",
            str(src),
            "--output",
            str(dst),
            "--placeholder",
            "abc123",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert dst.read_text(encoding="utf-8") == "A=abc123\nB=ok\n"
