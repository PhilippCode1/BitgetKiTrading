"""Stabiler SHA-256 Fingerprint aller SQL-Migrationen (Sortierung deterministisch)."""

from __future__ import annotations

import hashlib
from pathlib import Path


def compute_migrations_sha256(migrations_glob: Path) -> str:
    if not migrations_glob.is_dir():
        return ""
    h = hashlib.sha256()
    for p in sorted(migrations_glob.glob("*.sql"), key=lambda x: x.name):
        b = p.read_bytes()
        h.update(p.name.encode("utf-8", errors="replace"))
        h.update(b"::")
        h.update(b)
        h.update(b"||")
    return h.hexdigest()
