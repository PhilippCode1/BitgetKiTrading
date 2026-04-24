#!/usr/bin/env python3
"""
Vor Merge/Release-Tag: P0/P1+OPEN in docs/REPO_FREEZE_GAP_MATRIX.md (CI-Block),
einheitliche Versionsnummern (alle package.json + [project] version in pyproject.toml).

Exit 0: OK / 1: Blocker
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_MATRIX = _REPO / "docs" / "REPO_FREEZE_GAP_MATRIX.md"
_SKIP_PARTS = frozenset(
    {
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "target",
        ".next",
        "build",
        "coverage",
        ".turbo",
        "__pycache__",
        # Eigenes App-Shell/Generator-Tree; nicht mit Workspace-Root versionieren
        "Super_Bau_App",
    }
)


def _path_skip(p: Path) -> bool:
    return any(x in p.parts for x in _SKIP_PARTS)


def _md_row_cells(line: str) -> list[str]:
    parts = [p.strip() for p in line.split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return [re.sub(r"\*+", "", p).strip() for p in parts if p is not None]


def _check_freeze_matrix() -> list[str]:
    if not _MATRIX.is_file():
        return [f"FEHLT: {_MATRIX}"]

    text = _MATRIX.read_text(encoding="utf-8")
    marker = "## Monorepo CI — Freeze-Status (automatisiert, Merge-Gate)"
    if marker not in text:
        return [f"FEHLT Markierungsabschnitt: {marker!r} in {_MATRIX}"]

    after = text.split(marker, 1)[1]
    pidx, sidx = -1, -1
    bad: list[str] = []
    for line in after.splitlines():
        s = line.strip()
        if s.startswith("## ") and pidx >= 0:
            break
        if (
            pidx < 0
            and s.startswith("|")
            and re.search(r"\bPrio\b", s, re.I)
            and re.search(r"\bStatus\b", s, re.I)
        ):
            h = _md_row_cells(s)
            for i, h0 in enumerate(h):
                t = h0.replace("**", "").strip()
                if t == "Prio":
                    pidx = i
                if t == "Status":
                    sidx = i
            if pidx < 0 or sidx < 0:
                return [f"Tabellenkopf braucht Prio+Status: {h!r}"]
            continue
        if pidx < 0:
            continue
        if not s or not s.startswith("|"):
            continue
        if (
            re.match(r"^\|?\s*[-:–]+\s*\|", s)
            or re.match(r"^[\|:\s\-–]+[\+:-][\s\-:–|]+", s)
            or re.match(r"^[\s|:-]{3,}$", s)
            or s.replace("|", "").replace("-", "").replace(":", "").strip() == ""
        ):
            continue
        cells = _md_row_cells(s)
        if len(cells) <= max(pidx, sidx):
            continue
        praw = cells[pidx].upper()
        sraw = cells[sidx].upper()
        if praw in ("P0", "P1") and sraw == "OPEN":
            bad.append(f"  Prio={praw} Status=OPEN: {line.strip()[:220]!r}")
    if pidx < 0:
        return [f"Keine Header-Zeile (Prio|Status) in Freeze-Status: {_MATRIX}"]
    if bad:
        return ["P0/P1+OPEN in Monorepo-CI-Freeze-Tabelle (Merge blockiert):"] + bad
    return []


def _pyproject_version(path: Path) -> str:
    with path.open("rb") as f:
        d = tomllib.load(f)
    p = d.get("project")
    if not isinstance(p, dict) or "version" not in p:  # pragma: no cover
        raise ValueError(f"{path}: [project] version fehlt")
    return str(p["version"]).strip()


def _package_json_version(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "version" not in data:
        raise ValueError(f"{path}: version fehlt")
    return str(data["version"]).strip()


def _check_versions() -> list[str]:
    pjs: list[Path] = [p for p in _REPO.rglob("package.json") if not _path_skip(p)]
    tms: list[Path] = [p for p in _REPO.rglob("pyproject.toml") if not _path_skip(p)]
    if not tms or not pjs:
        return ["keine package.json / pyproject.toml (unerwartet)"]
    ref_py = _REPO / "pyproject.toml"
    ref_pj = _REPO / "package.json"
    if not ref_py.is_file() or not ref_pj.is_file():
        return ["Wurzel pyproject.toml + package.json erwartet"]
    v_py = _pyproject_version(ref_py)
    v_pj = _package_json_version(ref_pj)
    if v_py != v_pj:
        return [
            f"Version Root pyproject {v_py!r} != Root package.json {v_pj!r}",
        ]
    ref = v_py
    errs: list[str] = []
    for p in pjs:
        if p in (ref_pj,):
            continue
        try:
            v = _package_json_version(p)
        except (json.JSONDecodeError, ValueError) as exc:  # pragma: no cover
            errs.append(f"  {p}: {exc}")
            continue
        if v != ref:
            errs.append(f"  {p} version={v!r} (erwartet {ref!r} wie Root-Repo)")
    for p in tms:
        if p in (ref_py,):
            continue
        try:
            v = _pyproject_version(p)
        except (ValueError, OSError) as exc:  # pragma: no cover
            errs.append(f"  {p}: {exc}")
            continue
        if v != ref:
            errs.append(f"  {p} version={v!r} (erwartet {ref!r} wie Root-Repo)")
    if errs:
        return [f"Versionsdrift (alle package.json + pyproject.toml = {ref!r}):"] + errs
    return []


def main() -> int:
    a = _check_freeze_matrix()
    b = _check_versions()
    if a:
        print("FAIL: REPO_FREEZE / CI-Freeze-Status", file=sys.stderr, flush=True)
        print("\n".join(a), file=sys.stderr, flush=True)
    if b:
        print("FAIL: Monorepo-Versions-Einheitlichkeit", file=sys.stderr, flush=True)
        print("\n".join(b), file=sys.stderr, flush=True)
    if a or b:
        return 1
    print("OK: release-approval (Freeze+Version)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
