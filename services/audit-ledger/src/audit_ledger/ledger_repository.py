from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

from audit_ledger.config import AuditLedgerSettings
from audit_ledger.crypto_sign import ed25519_sign_chain_hash, ed25519_verify
from shared_py.audit_ledger_chain import GENESIS_CHAIN_HASH, ledger_chain_digest
from shared_py.observability.secret_leak_guard import scrub_audit_payload

logger = logging.getLogger("audit_ledger.repository")

_ADVISORY_LOCK_KEY = 902_410_719


@dataclass(frozen=True)
class CommitResult:
    decision_id: str
    chain_hash_hex: str
    prev_chain_hash_hex: str
    signature_hex: str
    public_key_hex: str


class LedgerRepository:
    def __init__(self, settings: AuditLedgerSettings) -> None:
        self._settings = settings
        self._dsn = settings.database_url.strip()
        if not self._dsn:
            raise ValueError("DATABASE_URL fehlt fuer audit-ledger")

    def commit_war_room(
        self,
        *,
        market_event_json: dict[str, Any],
        war_room: dict[str, Any],
    ) -> CommitResult:
        """Atomarer Commit: Advisory-Lock, letzter chain_hash, INSERT."""
        decision_id = uuid.uuid4()
        ts_ms = int(time.time() * 1000)
        safe_market = scrub_audit_payload(market_event_json, max_depth=6)
        safe_war = scrub_audit_payload(war_room, max_depth=8)
        record: dict[str, Any] = {
            "apex_decision_record_version": "1",
            "decision_id": str(decision_id),
            "recorded_ts_ms": ts_ms,
            "market_event_json": safe_market,
            "war_room": safe_war,
        }
        canonical = json.dumps(
            record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        canonical_bytes = canonical.encode("utf-8")

        seed = self._settings.ed25519_seed_32()

        with psycopg.connect(self._dsn) as conn:
            with conn.transaction():
                conn.execute("SELECT pg_advisory_xact_lock(%s)", (_ADVISORY_LOCK_KEY,))
                row = conn.execute(
                    "SELECT chain_hash FROM app.apex_audit_ledger_entries "
                    "ORDER BY id DESC LIMIT 1"
                ).fetchone()
                prev = row[0] if row and row[0] is not None else GENESIS_CHAIN_HASH
                if isinstance(prev, memoryview):
                    prev = prev.tobytes()
                if len(prev) != 32:
                    raise RuntimeError("Ungueltiger prev_chain_hash in DB")
                chain_hash = ledger_chain_digest(prev, canonical_bytes)
                sig, pub = ed25519_sign_chain_hash(seed, chain_hash)
                wrv = str(war_room.get("version") or "")
                cs = str(war_room.get("consensus_status") or "")
                fa = str(war_room.get("final_signal_action") or "")
                conn.execute(
                    """
                    INSERT INTO app.apex_audit_ledger_entries (
                        decision_id, prev_chain_hash, canonical_payload_text,
                        chain_hash, signature, signing_public_key,
                        war_room_version, consensus_status, final_signal_action
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        str(decision_id),
                        prev,
                        canonical,
                        chain_hash,
                        sig,
                        pub,
                        wrv or None,
                        cs,
                        fa,
                    ),
                )
        return CommitResult(
            decision_id=str(decision_id),
            chain_hash_hex=chain_hash.hex(),
            prev_chain_hash_hex=prev.hex(),
            signature_hex=sig.hex(),
            public_key_hex=pub.hex(),
        )

    def verify_full_chain(self) -> tuple[bool, list[str], int]:
        """Replay-Validation der gesamten Tabelle (aufsteigend nach ``id``)."""
        errors: list[str] = []
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            rows = conn.execute(
                "SELECT id, decision_id, prev_chain_hash, canonical_payload_text, "
                "chain_hash, signature, signing_public_key "
                "FROM app.apex_audit_ledger_entries ORDER BY id ASC"
            ).fetchall()
        prev_link = GENESIS_CHAIN_HASH
        for r in rows:
            prev_stored = r["prev_chain_hash"]
            if isinstance(prev_stored, memoryview):
                prev_stored = prev_stored.tobytes()
            ch_stored = r["chain_hash"]
            if isinstance(ch_stored, memoryview):
                ch_stored = ch_stored.tobytes()
            sig = r["signature"]
            if isinstance(sig, memoryview):
                sig = sig.tobytes()
            pub = r["signing_public_key"]
            if isinstance(pub, memoryview):
                pub = pub.tobytes()
            canon = str(r["canonical_payload_text"] or "").encode("utf-8")

            if prev_stored != prev_link:
                errors.append(
                    f"row id={r['id']}: prev_chain_hash bricht Kette "
                    f"(erwartet {prev_link.hex()}, gespeichert {prev_stored.hex()})"
                )
            recomputed = ledger_chain_digest(prev_stored, canon)
            if recomputed != ch_stored:
                errors.append(
                    f"row id={r['id']}: chain_hash Rekonstruktion mismatch "
                    f"(Payload-Manipulation oder falsche Spec)"
                )
            if not ed25519_verify(pub, sig, ch_stored):
                errors.append(f"row id={r['id']}: Ed25519-Signatur ungueltig")
            prev_link = ch_stored

        return (not errors, errors, len(rows))

    def list_entries_for_export(
        self,
        *,
        from_iso: str | None,
        to_iso: str | None,
        limit: int = 5000,
    ) -> list[dict[str, Any]]:
        q = (
            "SELECT decision_id::text AS decision_id, created_at, consensus_status, "
            "final_signal_action, encode(chain_hash, 'hex') AS chain_hash_hex, "
            "encode(prev_chain_hash, 'hex') AS prev_chain_hash_hex, "
            "encode(signature, 'hex') AS signature_hex "
            "FROM app.apex_audit_ledger_entries WHERE 1=1"
        )
        params: list[Any] = []
        if from_iso:
            q += " AND created_at >= %s"
            params.append(from_iso)
        if to_iso:
            q += " AND created_at <= %s"
            params.append(to_iso)
        q += " ORDER BY id ASC LIMIT %s"
        params.append(limit)
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            return list(conn.execute(q, params).fetchall())
