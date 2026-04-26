#!/usr/bin/env python3
"""
Repo-weiter Secret-Surface-Scan mit Redaction.

Findet potenzielle Secret-Leaks in Dateien (inkl. NEXT_PUBLIC-Namen) und schreibt
redigierte Reports als Markdown/JSON.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "config" / "required_secrets_matrix.json"

EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".cursor",
}

TEXT_FILE_SUFFIXES = {
    ".env",
    ".example",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".yaml",
    ".yml",
    ".md",
    ".txt",
    ".ini",
    ".cfg",
    ".toml",
    ".sh",
    ".ps1",
}

PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("openai_key", re.compile(r"sk-(?:proj|live|test|ant|or-v1)-[A-Za-z0-9_\-]{16,}"), "critical"),
    ("bearer_token", re.compile(r"Authorization\s*:\s*Bearer\s+[A-Za-z0-9._\-]{12,}", re.IGNORECASE), "high"),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "critical"),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "critical"),
    ("jwt_secret_assignment", re.compile(r"\bJWT_SECRET\s*=\s*[^\s#]{8,}"), "high"),
    ("internal_api_key_assignment", re.compile(r"\bINTERNAL_API_KEY\s*=\s*[^\s#]{8,}"), "high"),
    ("secret_key_assignment", re.compile(r"\bSECRET_KEY\s*=\s*[^\s#]{8,}"), "high"),
    ("passphrase_assignment", re.compile(r"\bPASSPHRASE\s*=\s*[^\s#]{8,}", re.IGNORECASE), "high"),
    ("token_assignment", re.compile(r"\bTOKEN\s*=\s*[^\s#]{8,}", re.IGNORECASE), "medium"),
    ("next_public_secret_name", re.compile(r"\bNEXT_PUBLIC_[A-Z0-9_]*(SECRET|TOKEN|API_KEY|JWT|PASSPHRASE)[A-Z0-9_]*\s*="), "critical"),
    ("bitget_secret", re.compile(r"\bBITGET_(?:DEMO_)?API_(?:KEY|SECRET|PASSPHRASE)\s*=\s*[^\s#]{8,}"), "high"),
)

@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    rule: str
    severity: str
    redacted_snippet: str


def _load_matrix_env_names() -> set[str]:
    if not MATRIX.is_file():
        return set()
    data = json.loads(MATRIX.read_text(encoding="utf-8"))
    entries = list(data.get("entries") or [])
    return {str(item.get("env", "")).strip() for item in entries if str(item.get("env", "")).strip()}


def _is_text_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_FILE_SUFFIXES:
        return True
    return path.name.startswith(".env")


def _redact(value: str) -> str:
    cleaned = re.sub(r"[A-Za-z0-9]", "*", value.strip())
    if len(cleaned) > 96:
        cleaned = cleaned[:96] + "..."
    return cleaned


def _scan_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return findings
    rel = path.relative_to(ROOT).as_posix()
    for idx, line in enumerate(lines, start=1):
        for rule_name, pattern, severity in PATTERNS:
            if rule_name == "next_public_secret_name" and not path.name.startswith(".env"):
                continue
            match = pattern.search(line)
            if not match:
                continue
            findings.append(
                Finding(
                    file=rel,
                    line=idx,
                    rule=rule_name,
                    severity=severity,
                    redacted_snippet=_redact(line),
                )
            )
    return findings


def _env_files_not_ignored() -> list[str]:
    out: list[str] = []
    for p in ROOT.rglob(".env*"):
        if p.is_dir():
            continue
        name = p.name
        if name.endswith(".example") or name == ".env.example":
            continue
        rel = p.relative_to(ROOT).as_posix()
        completed = subprocess.run(
            ["git", "check-ignore", rel],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            out.append(rel)
    return sorted(out)


def scan_repo() -> dict[str, Any]:
    findings: list[Finding] = []
    scanned_files = 0
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = set(path.relative_to(ROOT).parts)
        if rel_parts & EXCLUDED_DIRS:
            continue
        if not _is_text_file(path):
            continue
        scanned_files += 1
        findings.extend(_scan_file(path))
    matrix_keys = sorted(_load_matrix_env_names())
    env_not_ignored = _env_files_not_ignored()
    severity_counts = {"critical": 0, "high": 0, "medium": 0}
    for f in findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "scanned_files": scanned_files,
        "matrix_env_keys_count": len(matrix_keys),
        "matrix_env_keys_sample": matrix_keys[:20],
        "severity_counts": severity_counts,
        "findings": [asdict(f) for f in findings],
        "env_files_not_ignored": env_not_ignored,
        "critical_found": severity_counts.get("critical", 0) > 0 or bool(env_not_ignored),
    }


def _to_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Secret Surface Inventory",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- scanned_files: `{payload['scanned_files']}`",
        f"- critical: `{payload['severity_counts'].get('critical', 0)}`",
        f"- high: `{payload['severity_counts'].get('high', 0)}`",
        f"- medium: `{payload['severity_counts'].get('medium', 0)}`",
        f"- env_files_not_ignored: `{len(payload['env_files_not_ignored'])}`",
        "",
        "## Findings (redacted)",
        "",
        "| file | line | severity | rule | redacted_snippet |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for finding in payload["findings"][:500]:
        lines.append(
            f"| `{finding['file']}` | {finding['line']} | {finding['severity']} | `{finding['rule']}` | `{finding['redacted_snippet']}` |"
        )
    lines.append("")
    if payload["env_files_not_ignored"]:
        lines.append("## .env Not Ignored")
        lines.append("")
        for item in payload["env_files_not_ignored"]:
            lines.append(f"- `{item}`")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Repo Secret-Surface-Scan (redacted).")
    ap.add_argument(
        "--output-md",
        metavar="PATH",
        type=Path,
        help="Markdown-Report schreiben.",
    )
    ap.add_argument(
        "--output-json",
        metavar="PATH",
        type=Path,
        help="JSON-Report schreiben.",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Exit-Code 1 bei kritischen Funden.",
    )
    # Rueckwaertskompatibel
    ap.add_argument("--report-md", type=Path, help=argparse.SUPPRESS)
    ap.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    payload = scan_repo()
    output_md = args.output_md or args.report_md
    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(_to_md(payload), encoding="utf-8")
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    print(
        "secret_surface_inventory: "
        f"files={payload['scanned_files']} "
        f"critical={payload['severity_counts'].get('critical', 0)} "
        f"high={payload['severity_counts'].get('high', 0)} "
        f"env_not_ignored={len(payload['env_files_not_ignored'])}"
    )
    if args.strict and payload["critical_found"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
