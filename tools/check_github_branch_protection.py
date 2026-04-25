#!/usr/bin/env python3
"""
Branch-Protection gegen erwartete CI-Checks: Workflow `ci` in .github/workflows/ci.yml,
Job-Ids python, dashboard, compose_healthcheck, release-approval-gate.

Kontexte: typisch "ci / <job_id>" (GitHub Status-Check-Name).

Auth: GITHUB_TOKEN, GH_TOKEN, oder `gh auth token`. Ohne Auth:
UNKNOWN_NO_GITHUB_AUTH (in --strict: fehlgeschlagen).

KEIN fiktives PASS bei fehlendem Token oder fehlendem 200-API-Body.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final
from urllib.parse import quote

_WF: Final[str] = "ci"
MANDATORY: Final[tuple[str, ...]] = (
    "python",
    "dashboard",
    "compose_healthcheck",
    "release-approval-gate",
)
DEFAULT_REPO: Final[str] = "PhilippCode1/BitgetKiTrading"
GH_VERSION: Final[str] = "2022-11-28"
_UA: Final[str] = "bitget-ki-branch-protect/1.0"


@dataclass
class EvalResult:
    status: str
    pr_required: bool | None
    has_required_status_checks: bool
    release_approval_check_present: bool
    allow_force_pushes: bool | None
    allow_deletions: bool | None
    enforce_admins: bool | None
    block_direct_push_hint: str
    admin_bypass_note: str
    details: str
    required_contexts: list[str] = field(default_factory=list)
    missing_for_ci_yml: list[str] = field(default_factory=list)


def _token() -> str | None:
    t = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if t:
        return t
    try:
        p = subprocess.run(
            ["gh", "auth", "token"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if p.returncode == 0 and p.stdout:
            return p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None
    return None


def _parse_owner_repo(s: str) -> tuple[str, str]:
    r = s.strip()
    if r.count("/") != 1:
        raise SystemExit("Ungueltiges --repo, erwartet exakt owner/name (ein /).")
    a, b = r.split("/")
    if not a or not b:
        raise SystemExit("Ungueltiges --repo, erwartet owner/name.")
    return a.strip(), b.strip()


def _contexts(d: dict[str, Any]) -> list[str]:
    rsc = d.get("required_status_checks")
    if not isinstance(rsc, dict):
        return []
    out: list[str] = []
    ctx = rsc.get("contexts")
    if isinstance(ctx, list):
        for x in ctx:
            if isinstance(x, str) and x:
                out.append(x)
    for c in (rsc.get("checks") or ()):
        if isinstance(c, dict) and isinstance(c.get("context"), str):
            out.append(c["context"])
    seen: set[str] = set()
    d2: list[str] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            d2.append(x)
    return d2


def _pr_req(d: dict[str, Any]) -> bool | None:
    o = d.get("required_pull_request_reviews")
    if o is None:
        return None
    if isinstance(o, dict):
        if not o:
            return None
        n = o.get("required_approving_review_count")
        if n is not None and isinstance(n, int | float) and n >= 0 and len(o) > 0:
            return True
        return bool(o and len(o) > 0)
    return bool(o)


def _boolf(d: dict[str, Any], k: str) -> bool | None:
    b = d.get(k)
    if b is None:
        return None
    if isinstance(b, bool):
        return b
    if isinstance(b, dict) and isinstance(b.get("enabled"), bool):
        return bool(b["enabled"])
    return None


def _job_match(job: str, contexts: list[str]) -> bool:
    p = re.compile(
        re.escape(_WF) + r"\s*/\s*" + re.escape(job) + r"\s*\Z", re.IGNORECASE
    )
    for c in contexts:
        if p.search(c.strip()):
            return True
    return False


def evaluate(data: dict[str, Any]) -> EvalResult:
    rsc = data.get("required_status_checks")
    ctx = _contexts(data)
    if (rsc is None or (isinstance(rsc, dict) and not (rsc.get("contexts") or rsc.get("checks")))) and len(ctx) == 0:  # noqa: E501
        return EvalResult(
            status="UNKNOWN",
            pr_required=None,
            has_required_status_checks=False,
            required_contexts=[],
            missing_for_ci_yml=[*MANDATORY],
            release_approval_check_present=False,
            allow_force_pushes=None,
            allow_deletions=None,
            enforce_admins=None,
            block_direct_push_hint="unbekannt_ohne_check_kontexte",
            admin_bypass_note="payload_unvollstaendig_oder_403/404_oder_rulesets",
            details="rsc_und_kontexte_fehlend_oder_luecken",
        )
    has = bool(
        isinstance(rsc, dict)
        and (bool(rsc.get("contexts") or []) or bool(rsc.get("checks") or []))
    )
    if not has and len(ctx) > 0:
        has = True

    m = [j for j in MANDATORY if not _job_match(j, ctx)]
    rel = _job_match("release-approval-gate", ctx)
    prq = _pr_req(data)
    afp = _boolf(data, "allow_force_pushes")
    adel = _boolf(data, "allow_deletions")
    enf = _boolf(data, "enforce_admins")
    bhint = "merge_typischerweise_nur_mit_pr" if prq is True else (
        "direkter_push_moeglich_laut_prr" if prq is False
        else "unbekannt_ohne_prr_feld"
    )
    if isinstance(enf, bool):
        badmin = f"enforce_admins={enf!r}"
    else:
        badmin = "enforce_admins_unlesbar"
    d = f"m={m!r} rel={rel!r} prq={prq!r} afp={afp!r} n_ctx={len(ctx)}"

    if m or (not rel) or (afp is True) or (prq is False):
        st = "FAIL"
    elif prq is None:
        st = "UNKNOWN"
    else:
        st = "PASS"

    return EvalResult(
        status=st,
        pr_required=prq,
        has_required_status_checks=has,
        required_contexts=ctx,
        missing_for_ci_yml=m,
        release_approval_check_present=rel,
        allow_force_pushes=afp,
        allow_deletions=adel,
        enforce_admins=enf,
        block_direct_push_hint=bhint,
        admin_bypass_note=badmin,
        details=d,
    )


def eval_noauth() -> EvalResult:
    return EvalResult(
        status="UNKNOWN_NO_GITHUB_AUTH",
        pr_required=None,
        has_required_status_checks=False,
        required_contexts=[],
        missing_for_ci_yml=[],
        release_approval_check_present=False,
        allow_force_pushes=None,
        allow_deletions=None,
        enforce_admins=None,
        block_direct_push_hint="unpruefbar_ohne_token_oder_gh",
        admin_bypass_note="TOKEN/GH_TOKEN oder gh; read scope; kein pass",
        details="no_auth",
    )


def _fetch(
    o: str, n: str, b: str, t: str
) -> tuple[dict[str, Any] | None, int, str]:
    u = f"https://api.github.com/repos/{o}/{n}/branches/{quote(b, safe='')}/protection"
    req = urllib.request.Request(  # noqa: S310
        u,
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GH_VERSION,
            "User-Agent": _UA,
            "Authorization": f"Bearer {t}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as r:  # noqa: S310
            body = r.read().decode("utf-8", errors="replace")
            return json.loads(body), r.getcode() or 200, ""
    except urllib.error.HTTPError as e:  # noqa: PERF203
        s = e.read().decode("utf-8", errors="replace")
        return None, int(e.code), s[:2000]
    except OSError as e:  # noqa: PERF203
        return None, 0, str(e)[:2000]

def _offline(path: Path) -> dict[str, Any]:
    p = json.loads(path.read_text(encoding="utf-8"))
    d = p.get("data", p) if isinstance(p, dict) else {}
    if not isinstance(d, dict):
        return {}
    return d


def run(
    repo: str,
    branch: str,
    fixture: Path | None,
    token_opt: str | None,
) -> tuple[EvalResult, str | None]:
    if fixture and fixture.is_file():
        d = _offline(fixture)
        return evaluate(d), f"offline_file:{fixture.name}"
    t = (token_opt or _token() or "").strip()
    if not t:
        return eval_noauth(), "no_token"
    o, n_ = _parse_owner_repo(repo)
    data, code, em = _fetch(o, n_, branch, t)
    if data is not None and code == 200:
        return evaluate(data), "api_200"
    e = (
        f"api_http={code!r} body={em[:1200]!r}" if em else f"api_code={code!r}"
    )
    return EvalResult(
        status="UNKNOWN",
        pr_required=None,
        has_required_status_checks=False,
        required_contexts=[],
        missing_for_ci_yml=[],
        release_approval_check_present=False,
        allow_force_pushes=None,
        allow_deletions=None,
        enforce_admins=None,
        block_direct_push_hint="nur_200_lesen_wertet_aus",
        admin_bypass_note=e[:2000],
        details=e[:2000],
    ), e


def _to_md(
    e: EvalResult, repo: str, branch: str, meta: str | None, strict: bool
) -> str:
    a: dict[str, object] = {
        **asdict(e),
        "repo": repo,
        "branch": branch,
        "strict": strict,
        "meta": meta,
    }
    j = json.dumps(a, ensure_ascii=False, indent=2)
    meta_s = f"{meta!r}"
    strict_s = f"{strict!s}"
    line_meta = f"**repo** `{repo}` **branch** `{branch}`" + (
        f" **meta** {meta_s} **strict** {strict_s}  "
    )
    return "\n".join(
        [
            "# GitHub Branch-Protection (Repo-Werkzeug)",
            "",
            f"**Status:** `{e.status}`  ",
            f"**Erwartet (Workflow-Job-Ids, wf=`{_WF}`):** {list(MANDATORY)!r}  ",
            line_meta,
            f"**details:** {e.details}  ",
            f"**JSON:**\n\n```json\n{j}\n```\n",
        ]
    )

def _exit(strict: bool, s: str) -> int:
    if not strict:
        return 0
    return 0 if s == "PASS" else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Prueft Branch-Protection vs. ci-Workflow-Job-Kontexte "
            "(GitHub API/Offline JSON)."
        ),
    )
    d_repo = (os.environ.get("GITHUB_REPOSITORY") or "").strip() or DEFAULT_REPO
    ap.add_argument(
        "--repo",
        default=d_repo,
        help="owner/repository, default: GITHUB_REPOSITORY|DEFAULT in Skript",
    )
    ap.add_argument("--branch", default="main")
    ap.add_argument("--offline-fixture", type=Path, default=None, dest="off")
    ap.add_argument("--report-md", type=Path, default=None)
    ap.add_argument(
        "--json", type=Path, default=None, dest="jsonp", help="Voll-JSON-Report-Datei"
    )
    ap.add_argument(
        "--token", default=None, help="sonst GITHUB_TOKEN / GH_TOKEN / gh"
    )
    ap.add_argument(
        "--strict", action="store_true", help="exit 1 wenn status != PASS"
    )
    a = ap.parse_args()
    e, m = run(a.repo, a.branch, a.off, a.token)
    b = {
        **asdict(e),
        "meta": m,
        "strict": a.strict,
        "exit_code": _exit(a.strict, e.status),
    }
    js = json.dumps(b, ensure_ascii=False, indent=2) + "\n"
    if a.jsonp:
        a.jsonp.parent.mkdir(parents=True, exist_ok=True)
        a.jsonp.write_text(js, encoding="utf-8")
    if a.report_md:
        a.report_md.parent.mkdir(parents=True, exist_ok=True)
        a.report_md.write_text(
            _to_md(e, a.repo, a.branch, m, a.strict),
            encoding="utf-8",
        )
    if a.jsonp is None and a.report_md is None:
        print(js)
    return int(b["exit_code"])


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
