"""
Hash-Kette fuer Apex Predator Audit Ledger.

Spec (Rust ``apex_audit_ledger``): ``chain_hash = SHA256(prev_chain_hash || canonical_payload_utf8)``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

GENESIS_CHAIN_HASH: bytes = bytes(32)


def canonical_json_bytes(obj: Any) -> bytes:
    """Deterministische JSON-Serialisierung (UTF-8)."""
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return s.encode("utf-8")


def ledger_chain_digest(prev_chain_hash: bytes, canonical_payload_utf8: bytes) -> bytes:
    if len(prev_chain_hash) != 32:
        raise ValueError("prev_chain_hash muss 32 Byte lang sein")
    h = hashlib.sha256()
    h.update(prev_chain_hash)
    h.update(canonical_payload_utf8)
    return h.digest()
