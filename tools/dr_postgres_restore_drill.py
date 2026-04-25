#!/usr/bin/env python3
"""
Postgres-Backup/Restore-Drill: isoliertes Schema, pg_dump, psql, Checksumme.

Kein PASS ohne laufende DB und Client-Tools (pg_dump, ps, psycopg).
Dry-run: Tool- und optional Verbindungs-Check, ohne Schema-Mutation bei fehlendem
DSN; mit DSN nur connect + keine Schreib-Operationen (siehe main).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import psycopg
    from psycopg import sql
except ImportError:  # pragma: no cover
    psycopg = None  # type: ignore[assignment]
    sql = None  # type: ignore[assignment]


@dataclass
class DrillResult:
    status: str
    message: str
    schema_name: str
    dsn_sanitized: str
    git_sha: str
    rto_sec: float | None
    rpo_model_sec: float | None
    total_sec: float
    before_sha256: str
    after_sha256: str
    checksums_match: bool
    rto_gate_ok: bool
    rpo_gate_ok: bool
    require_rto_sec: float | None
    require_rpo_sec: float | None
    dry_run: bool
    details: str
    tool_check: list[str] = field(default_factory=list)


def _redact_dsn(d: str) -> str:
    if not d or "@" not in d or "://" not in d:
        return d[:32] if len(d) < 50 else d[:20] + "…"
    return re.sub(
        r"(?i)([a-z+]+://[^:]+:)([^@]+)(@)",
        r"\1***\3",
        d,
        count=1,
    )


def _read_env_dsn(p: Path, prefer_test: bool) -> str | None:
    t = p.read_text(encoding="utf-8", errors="replace")
    k = "TEST_DATABASE_URL" if prefer_test else "DATABASE_URL"
    m = re.search(rf"^{re.escape(k)}=(.*)$", t, re.M)
    if not m and not prefer_test:
        m2 = re.search(r"^TEST_DATABASE_URL=(.*)$", t, re.M)
        m = m2
    if not m:
        return None
    s = m.group(1).strip()
    if s.startswith(('"', "'")):
        s = s[1:-1] if len(s) >= 2 and s[0] == s[-1] else s
    s = s.split("#", 1)[0].strip()
    return s or None


def _check_tools() -> list[str]:
    m: list[str] = []
    for t in ("pg_dump", "psql"):
        if not shutil.which(t) and not shutil.which(t + ".exe"):
            m.append(t)
    if psycopg is None:
        m.append("python-psycopg")
    return m


def _row_checksum(conn: Any, sc: str) -> str:
    assert sql is not None
    h = hashlib.sha256()
    with conn.cursor() as c:
        c.execute(
            sql.SQL(
                "SELECT id, payload, inserted_at::text FROM {}.drill_t ORDER BY id"
            ).format(sql.Identifier(sc))
        )
        for rid, pl, it in c.fetchall() or ():
            h.update(f"{rid}|{pl}|{it}\n".encode())
    return h.hexdigest()


def _run_sub(
    args: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None
) -> tuple[int, str, str]:
    p = subprocess.run(  # noqa: S603
        args, capture_output=True, text=True, env=env or None, timeout=600, cwd=cwd
    )
    o = (p.stdout or "") + (p.stderr or "")
    return p.returncode, o, o[:8000]


def _git_sha() -> str:
    s = (os.environ.get("GITHUB_SHA") or os.environ.get("CI_COMMIT_SHA") or "").strip()
    if len(s) >= 7:
        return s[:40]
    try:
        p = subprocess.run(  # noqa: S603
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parents[1],
            timeout=5,
        )
        if p.returncode == 0 and p.stdout:
            return p.stdout.strip()[:40]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "unbekannt"


def run_drill(
    dsn: str,
    artifact_dir: Path,
    dry_run: bool,
    rto_max: float | None,
    rpo_max: float | None,
) -> DrillResult:
    missing = _check_tools()
    sha = _git_sha()
    san = _redact_dsn(dsn)
    t0 = time.perf_counter()
    if missing:
        return DrillResult(
            status="MISSING_TOOL",
            message="pg_dump und/oder psql (PATH) bzw. psycopg fehlt",
            schema_name="",
            dsn_sanitized=san,
            git_sha=sha,
            rto_sec=None,
            rpo_model_sec=None,
            total_sec=time.perf_counter() - t0,
            before_sha256="",
            after_sha256="",
            checksums_match=False,
            rto_gate_ok=False,
            rpo_gate_ok=False,
            require_rto_sec=rto_max,
            require_rpo_sec=rpo_max,
            dry_run=dry_run,
            details=",".join(missing),
            tool_check=missing,
        )
    if dry_run:
        try:
            c = psycopg.connect(dsn)  # type: ignore[union-attr]
            c.close()
            okm = "connect_ok"
        except Exception as e:  # noqa: BLE001
            okm = f"connect_fail: {e!r}"
        return DrillResult(
            status="DRYRUN_OK" if "ok" in okm else "UNKNOWN",
            message=okm,
            schema_name="(keine_schema_aktion_dryrun)",
            dsn_sanitized=san,
            git_sha=sha,
            rto_sec=None,
            rpo_model_sec=None,
            total_sec=time.perf_counter() - t0,
            before_sha256="",
            after_sha256="",
            checksums_match="ok" in okm,
            rto_gate_ok=True,
            rpo_gate_ok=True,
            require_rto_sec=rto_max,
            require_rpo_sec=rpo_max,
            dry_run=True,
            details=okm,
            tool_check=[],
        )

    tag = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
    sc = f"dr_restore_drill_{tag}"
    assert sql is not None
    art = artifact_dir
    art.mkdir(parents=True, exist_ok=True)
    dump = art / f"pg_dump_{tag}.sql"
    logf = art / f"drill_log_{tag}.json"

    try:
        conn = psycopg.connect(dsn, autocommit=True)  # type: ignore[union-attr]
    except Exception as e:  # noqa: BLE001
        return DrillResult(
            status="MISSING_DATABASE",
            message=f"verbindung_fehlgeschlagen: {e!r}",
            schema_name=sc,
            dsn_sanitized=san,
            git_sha=sha,
            rto_sec=None,
            rpo_model_sec=None,
            total_sec=time.perf_counter() - t0,
            before_sha256="",
            after_sha256="",
            checksums_match=False,
            rto_gate_ok=False,
            rpo_gate_ok=False,
            require_rto_sec=rto_max,
            require_rpo_sec=rpo_max,
            dry_run=False,
            details=str(e)[:2000],
            tool_check=[],
        )
    t_insert_start = time.perf_counter()
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(sc))
        )
        cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(sc)))
        cur.execute(
            sql.SQL(
                "CREATE TABLE {}.drill_t ("
                "id serial primary key, payload text not null, "
                "inserted_at timestamptz not null default now())"
            ).format(sql.Identifier(sc))
        )
    secret = f"row_{uuid.uuid4().hex}"
    with conn.cursor() as c:
        c.execute(
            sql.SQL("INSERT INTO {}.drill_t (payload) VALUES (%s)").format(
                sql.Identifier(sc)
            ),
            (secret,),
        )
    csum0 = _row_checksum(conn, sc)
    rc, o, _ = _run_sub(
        [
            "pg_dump",
            "-F",
            "p",
            "-f",
            str(dump),
            "-n",
            sc,
            "-d",
            dsn,
        ]
    )
    t_after_dump = time.perf_counter()
    rpo2 = t_after_dump - t_insert_start
    if rc != 0 or not dump.is_file() or dump.stat().st_size == 0:
        conn.close()
        return DrillResult(
            status="FAIL",
            message=f"pg_dump fehlgeschlagen: rc={rc} {o[:2000]!r}",
            schema_name=sc,
            dsn_sanitized=san,
            git_sha=sha,
            rto_sec=None,
            rpo_model_sec=rpo2,
            total_sec=time.perf_counter() - t0,
            before_sha256=csum0,
            after_sha256="",
            checksums_match=False,
            rto_gate_ok=not (rto_max and False),
            rpo_gate_ok=not (rpo_max and rpo2 > rpo_max) if rpo_max else True,
            require_rto_sec=rto_max,
            require_rpo_sec=rpo_max,
            dry_run=False,
            details=o[:4000],
            tool_check=[],
        )

    with conn.cursor() as c:
        c.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(sc)))
    conn.close()
    tr = time.perf_counter()
    o2 = ""
    rc2, o2, _ = _run_sub(
        [
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-d",
            dsn,
            "-f",
            str(dump),
        ]
    )
    t_after_restore = time.perf_counter()
    rto = t_after_restore - tr

    c2: Any = None
    csum1 = ""
    try:
        c2 = psycopg.connect(dsn)  # type: ignore[union-attr]
        csum1 = _row_checksum(c2, sc)
    except Exception as e:  # noqa: BLE001
        o2 = (o2 or "") + f" checksum_fail: {e!r}"

    match = csum0 == csum1 and bool(csum1) and not rc2
    st = "PASS" if (match and rc2 == 0) else "FAIL"
    rto_ok = (rto_max is None) or (rto <= rto_max)
    rpo_ok = (rpo_max is None) or (rpo2 <= rpo_max)
    rpo3 = rpo2
    rto_use = rto

    d_out = {
        "version": 1,
        "schema": sc,
        "dump_size_bytes": dump.stat().st_size,
        "pg_dump_rc": rc,
        "psql_rc": rc2,
        "rto_sec_measured": rto_use,
        "rpo_sec_model": rpo3,
    }
    logf.write_text(json.dumps(d_out, ensure_ascii=False, indent=2), encoding="utf-8")
    hsum = hashlib.sha256()
    hsum.update(dump.read_bytes())
    sha_line = f"{hsum.hexdigest()}  {dump.name}\n"
    (art / f"dump_{tag}.sha256").write_text(sha_line, encoding="utf-8")

    msg = "drill_alle_schritte" if st == "PASS" else f"rc_psql={rc2} match={match}"
    if not rto_ok or not rpo_ok:
        st = "FAIL"
        msg += f" gate rto={rto_ok!r} rpo={rpo_ok!r}"

    if c2 is not None and st == "PASS" and sql is not None:
        try:
            c2.autocommit = True
            with c2.cursor() as cur:
                cur.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(sc)
                    )
                )
        except Exception:  # noqa: BLE001,S110
            pass
    if c2 is not None:
        try:
            c2.close()
        except Exception:  # noqa: BLE001,S110
            pass

    tot = time.perf_counter() - t0
    return DrillResult(
        status=st,
        message=msg,
        schema_name=sc,
        dsn_sanitized=san,
        git_sha=sha,
        rto_sec=rto_use,
        rpo_model_sec=rpo3,
        total_sec=tot,
        before_sha256=csum0,
        after_sha256=csum1,
        checksums_match=bool(match),
        rto_gate_ok=rto_ok,
        rpo_gate_ok=rpo_ok,
        require_rto_sec=rto_max,
        require_rpo_sec=rpo_max,
        dry_run=False,
        details=o2[:5000] if o2 else "",
        tool_check=[],
    )


def render_md(r: DrillResult) -> str:
    lines = [
        "# Postgres DR-Restore-Drill",
        "",
        f"**Status:** `{r.status}`  ",
        f"**Message:** {r.message}  ",
        f"**Time (UTC):** {datetime.now(UTC).isoformat()}  ",
        f"**DSN (sanitisiert):** `{r.dsn_sanitized}`  ",
        f"**Schema:** `{r.schema_name}`  ",
        f"**git_sha (Env/Repo):** `{r.git_sha}`  ",
        f"**dry_run:** {r.dry_run}  ",
        f"**Checksumme vor (Zeilen-Hash):** `{r.before_sha256}`  ",
        f"**Checksumme nach:** `{r.after_sha256}`  ",
        f"**match:** {r.checksums_match}  ",
        f"**RTO_sec (Restore-Phase, gemessen):** {r.rto_sec!r}  ",
        f"**RPO-Modell-Sek. (last_write→pg_dump_fertig):** {r.rpo_model_sec!r}  ",
        f"**Gates:** require_rto={r.require_rto_sec!r} rto_ok={r.rto_gate_ok} | "
        f"require_rpo={r.require_rpo_sec!r} rpo_ok={r.rpo_gate_ok}  ",
        f"**total_sec:** {r.total_sec:.3f}  ",
    ]
    if r.tool_check:
        lines.append(f"**Fehlende tools:** {r.tool_check!r}  ")
    if r.details and len(r.details) < 4000:
        lines.append(f"**Details:**\n\n```\n{r.details}\n```\n")
    lines.append(
        "\n*Kein `PASS` fuer institutionelles L4 ohne reale, archivierte Ausfuehrung; "
        "Lokalrechner-Drill ersetzt nicht Staging-Prod-Analogie.*\n"
    )
    return "\n".join(lines)


def _exit(r: str) -> int:
    if r in ("PASS", "DRYRUN_OK"):
        return 0
    return 1


def _write_outputs(r: DrillResult, art: Path, outmd: Path | None) -> None:
    t = render_md(r)
    if outmd is not None:
        outmd.parent.mkdir(parents=True, exist_ok=True)
        outmd.write_text(t, encoding="utf-8")
    else:
        print(t)
    art.mkdir(parents=True, exist_ok=True)
    (art / "result.json").write_text(
        json.dumps(asdict(r), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Postgres-Schema-DR-Drill: dump, drop, psql, checksum"
    )
    ap.add_argument("--env-file", type=Path, default=None)
    ap.add_argument(
        "--prefer-test-url",
        action="store_true",
        help="Liest zuerst TEST_DATABASE_URL, sonst DATABASE_URL",
    )
    ap.add_argument("--database-url", type=str, default=None)
    ap.add_argument("--output-md", type=Path, default=None, dest="outmd")
    ap.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        dest="artd",
        help="Dump, .sha256, result.json, drill_log_*.json",
    )
    ap.add_argument("--dry-run", action="store_true", dest="dry")
    ap.add_argument("--require-rto-sec", type=float, default=None)
    ap.add_argument("--require-rpo-sec", type=float, default=None)
    a = ap.parse_args()
    art = a.artd or Path("artifacts") / f"dr_restore_drill_{int(time.time())}"

    dsn = (a.database_url or "").strip() or None
    if a.env_file and a.env_file.is_file() and dsn is None:
        dsn = _read_env_dsn(a.env_file, a.prefer_test_url)

    if a.dry:
        if dsn is None:
            m = _check_tools()
            r = DrillResult(
                status="DRYRUN_OK" if not m else "MISSING_TOOL",
                message="dry_run: nur_werkzeug" if not m else "fehlend:" + ",".join(m),
                schema_name="(n/a)",
                dsn_sanitized="(kein dsn)",
                git_sha=_git_sha(),
                rto_sec=None,
                rpo_model_sec=None,
                total_sec=0.0,
                before_sha256="",
                after_sha256="",
                checksums_match=not m,
                rto_gate_ok=not m,
                rpo_gate_ok=not m,
                require_rto_sec=a.require_rto_sec,
                require_rpo_sec=a.require_rpo_sec,
                dry_run=True,
                details=",".join(m) if m else "ok",
                tool_check=m,
            )
            _write_outputs(r, art, a.outmd)
            return _exit(r.status)

        r = run_drill(dsn, art, True, a.require_rto_sec, a.require_rpo_sec)
        _write_outputs(r, art, a.outmd)
        return _exit(r.status)

    if dsn is None:
        r = DrillResult(
            status="MISSING_DATABASE",
            message="--database-url oder Wert in --env-file",
            schema_name="",
            dsn_sanitized="(none)",
            git_sha=_git_sha(),
            rto_sec=None,
            rpo_model_sec=None,
            total_sec=0.0,
            before_sha256="",
            after_sha256="",
            checksums_match=False,
            rto_gate_ok=False,
            rpo_gate_ok=False,
            require_rto_sec=a.require_rto_sec,
            require_rpo_sec=a.require_rpo_sec,
            dry_run=False,
            details="",
            tool_check=[],
        )
        _write_outputs(r, art, a.outmd)
        return 1

    r = run_drill(dsn, art, False, a.require_rto_sec, a.require_rpo_sec)
    _write_outputs(r, art, a.outmd)
    return _exit(r.status)


if __name__ == "__main__":
    raise SystemExit(main())
