#!/usr/bin/env python3
"""
Supply-Chain-Gate fuer Python: pip-audit (requirements-dev +
constraints-runtime) + OSV + CVSS.

Policy (wie pnpm --audit-level=high): CVSS-3.1-**Base** >= **7.0** oder
GitHub-Label **HIGH**/**CRITICAL** in OSV → CI-Fehler, sofern nicht in
tools/pip_audit_allowlist.txt.

Allowlist: eine Vulnerability-ID pro Zeile (GHSA-*, CVE-*, PYSEC-*), # Kommentare.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from cvss import CVSS3

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_PATH = ROOT / "tools" / "pip_audit_allowlist.txt"
REQUIREMENT_FILES: tuple[Path, ...] = (
    ROOT / "requirements-dev.txt",
    ROOT / "constraints-runtime.txt",
)
OSV_URL = "https://api.osv.dev/v1/vulns/"

_FAIL_MIN_BASE = 7.0

_SEVERITY_LABEL_RANK = {
    "LOW": 0,
    "MODERATE": 1,
    "MEDIUM": 1,
    "HIGH": 2,
    "CRITICAL": 3,
}


def _load_allowlist(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    out: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            out.add(line)
    return out


def _cvss_base_score(vector: str) -> float | None:
    try:
        c = CVSS3(vector)
        return float(c.base_score)
    except Exception:
        return None


def _osv_fail_rank(data: dict[str, object]) -> int | None:
    """Return None if below gate; 2 if meets HIGH gate; 3 if critical band."""
    ds = data.get("database_specific")
    if isinstance(ds, dict):
        sev = ds.get("severity")
        if isinstance(sev, str):
            r = _SEVERITY_LABEL_RANK.get(sev.upper())
            if r is not None and r >= 2:
                return 3 if r >= 3 else 2
    sev_list = data.get("severity")
    if isinstance(sev_list, list):
        best = 0.0
        for item in sev_list:
            if not isinstance(item, dict):
                continue
            score = item.get("score")
            if isinstance(score, str) and score.startswith("CVSS:3"):
                bs = _cvss_base_score(score)
                if bs is not None:
                    best = max(best, bs)
        if best >= 9.0:
            return 3
        if best >= _FAIL_MIN_BASE:
            return 2
    return None


def _fetch_osv(vid: str) -> dict[str, object] | None:
    url = OSV_URL + urllib.parse.quote(vid, safe="")
    ua = "bitget-btc-ai-ci-pip-audit-gate"
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except Exception:
        return None


def _resolve_osv(vid: str, aliases: list[str]) -> dict[str, object] | None:
    for candidate in [vid, *aliases]:
        if not candidate:
            continue
        data = _fetch_osv(candidate)
        if data is not None:
            return data
    return None


def _run_pip_audit() -> dict[str, object]:
    cmd = [
        sys.executable,
        "-m",
        "pip_audit",
        "--format",
        "json",
        "--aliases",
        "on",
    ]
    for req in REQUIREMENT_FILES:
        if not req.is_file():
            rel = req.relative_to(ROOT)
            raise SystemExit(f"pip_audit_supply_chain_gate: fehlt {rel}")
        cmd.extend(["-r", str(req)])
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in (0, 1):
        print(proc.stdout, file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(f"pip-audit failed with exit {proc.returncode}")
    return json.loads(proc.stdout or "{}")


def main() -> int:
    allow = _load_allowlist(ALLOWLIST_PATH)
    report = _run_pip_audit()
    deps = report.get("dependencies")
    if not isinstance(deps, list):
        print("pip-audit: keine dependencies in JSON", file=sys.stderr)
        return 1

    violations: list[str] = []
    cache: dict[str, int | None] = {}

    for dep in deps:
        if not isinstance(dep, dict) or "skip_reason" in dep:
            continue
        name = dep.get("name", "?")
        version = dep.get("version", "?")
        vulns = dep.get("vulns", [])
        if not isinstance(vulns, list):
            continue
        for v in vulns:
            if not isinstance(v, dict):
                continue
            vid = str(v.get("id", ""))
            raw_aliases = v.get("aliases", [])
            if isinstance(raw_aliases, list):
                aliases = [str(a) for a in raw_aliases if a]
            else:
                aliases = []
            alias_set = {vid, *aliases}
            if allow.intersection(alias_set):
                continue
            if not vid:
                continue
            if vid not in cache:
                osv = _resolve_osv(vid, aliases)
                if osv is None:
                    cache[vid] = 2
                else:
                    cache[vid] = _osv_fail_rank(osv)
            rank = cache[vid]
            if rank is not None:
                violations.append(f"  {name}@{version}: {vid} (OSV/CVSS gate)")

    if violations:
        msg = (
            "pip_audit_supply_chain_gate: HIGH/Critical "
            "(CVSS>=7 oder Label) ohne Allowlist:"
        )
        print(msg, file=sys.stderr)
        print("\n".join(violations), file=sys.stderr)
        print(
            f"Dokumentierte Ausnahmen: {ALLOWLIST_PATH.relative_to(ROOT)}",
            file=sys.stderr,
        )
        return 1
    print("OK pip_audit_supply_chain_gate: keine High/Critical ausser Allowlist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
