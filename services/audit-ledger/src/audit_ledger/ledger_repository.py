from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from audit_ledger.config import AuditLedgerSettings
from audit_ledger.crypto_sign import ed25519_sign_chain_hash, ed25519_verify
from shared_py.audit_ledger_chain import GENESIS_CHAIN_HASH, ledger_chain_digest
from shared_py.observability.apex_trade_forensic_store import (
    expected_previous_chain_for_row,
    fetch_apex_trade_forensic_row,
    upsert_apex_trade_forensic,
    verify_row_integrity,
)
from shared_py.observability.ledger_decision_package import build_ledger_decision_package
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
        forensic = build_ledger_decision_package(
            market_event_json=safe_market, war_room=safe_war
        )
        record: dict[str, Any] = {
            "apex_decision_record_version": "2",
            "decision_id": str(decision_id),
            "recorded_ts_ms": ts_ms,
            "market_event_json": safe_market,
            "war_room": safe_war,
            "forensic_decision_package": forensic,
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

    def upsert_apex_latency(
        self,
        *,
        signal_id: str,
        execution_id: str | None,
        trace_id: str | None,
        apex_trace: dict[str, Any],
    ) -> None:
        """app.apex_latency_audit — gleiche Semantik wie live-broker.repo.upsert."""
        if not (signal_id or "").strip() or not isinstance(apex_trace, dict) or not apex_trace:
            return
        eid = None
        if execution_id:
            try:
                eid = uuid.UUID(str(execution_id))
            except (TypeError, ValueError):
                eid = None
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                """
                INSERT INTO app.apex_latency_audit (signal_id, execution_id, trace_id, apex_trace, updated_at)
                VALUES (%(sid)s, %(eid)s, %(tid)s, %(apex)s, now())
                ON CONFLICT (signal_id) DO UPDATE SET
                    execution_id = COALESCE(EXCLUDED.execution_id, app.apex_latency_audit.execution_id),
                    trace_id = EXCLUDED.trace_id,
                    apex_trace = EXCLUDED.apex_trace,
                    updated_at = now()
                """,
                {
                    "sid": signal_id.strip()[:2000],
                    "eid": eid,
                    "tid": (str(trace_id).strip() or None) if trace_id else None,
                    "apex": Json(apex_trace),
                },
            )

    def fetch_apex_by_signal_id(self, signal_id: str) -> dict[str, Any] | None:
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            r = conn.execute(
                "SELECT * FROM app.apex_latency_audit WHERE signal_id = %s LIMIT 1",
                (signal_id.strip()[:2000],),
            ).fetchone()
        if r is None:
            return None
        row = dict(r)
        if "apex_trace" in row and isinstance(row["apex_trace"], str):
            try:
                row["apex_trace"] = json.loads(row["apex_trace"])
            except json.JSONDecodeError:
                pass
        return row

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

    def commit_trade_lifecycle_golden(
        self,
        *,
        execution_id: str,
        signal_id: str | None,
        golden_record: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Schreibt app.apex_trade_forensics (Hash-Kette, siehe shared_py.apex_trade_forensic_store)."""
        with psycopg.connect(self._dsn) as conn:
            return upsert_apex_trade_forensic(
                conn, execution_id=execution_id, signal_id=signal_id, golden_record=golden_record
            )

    def fetch_trade_forensic_export(
        self, execution_id: str
    ) -> dict[str, Any] | None:
        """Liest Golden Record inkl. is_verified fuer eine execution_id."""
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            row = fetch_apex_trade_forensic_row(conn, execution_id=execution_id)
            if not row:
                return None
            try:
                rid = int(row["id"])
            except (TypeError, KeyError, ValueError):
                return {**row, "verification": {"is_verified": False}}
            expect_prev = expected_previous_chain_for_row(conn, row_id=rid)
            v = verify_row_integrity(row, expected_prev_link=expect_prev)
            ccs = row.get("chain_checksum")
            pcs = row.get("prev_chain_checksum")
            if isinstance(ccs, memoryview):
                ccs = ccs.tobytes()
            if isinstance(pcs, memoryview):
                pcs = pcs.tobytes()
            return {
                "execution_id": row.get("execution_id"),
                "signal_id": row.get("signal_id"),
                "created_at": row.get("created_at"),
                "golden_record": row.get("golden_record"),
                "chain_checksum_hex": ccs.hex() if isinstance(ccs, bytes) else None,
                "prev_chain_checksum_hex": pcs.hex() if isinstance(pcs, bytes) else None,
                "is_verified": v.get("is_verified"),
                "verification": v,
            }

    def verify_chain_last_n(self, n: int = 1000) -> tuple[bool, list[str], int, int | None]:
        """
        Wie verify_full_chain, nur fuer die letzten n Eintraege (id absteigend);
        reicht vorigen Kettenglied-Knoten aus dem DB-Parent aus.
        """
        n = max(1, min(n, 1_000_000))
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            rows = list(
                conn.execute(
                    """
                    SELECT id, decision_id, prev_chain_hash, canonical_payload_text,
                           chain_hash, signature, signing_public_key
                    FROM app.apex_audit_ledger_entries
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (n,),
                ).fetchall()
            )
        rows = list(reversed(rows))
        errors: list[str] = []
        if not rows:
            return True, [], 0, None
        first_id: int = int(rows[0]["id"])
        prev_link = GENESIS_CHAIN_HASH
        if first_id > 1:
            with psycopg.connect(self._dsn, row_factory=dict_row) as conn2:
                prow = conn2.execute(
                    "SELECT chain_hash FROM app.apex_audit_ledger_entries "
                    "WHERE id = %s",
                    (first_id - 1,),
                ).fetchone()
            if not prow or prow.get("chain_hash") is None:
                errors.append(
                    f"window: Parent-Zeile id={first_id - 1} fehlt; Kettenglied ab id={first_id} nicht pruefbar"
                )
            else:
                pbt = prow["chain_hash"]
                if isinstance(pbt, memoryview):
                    pbt = pbt.tobytes()
                prev_link = pbt
        if errors:
            return (False, errors, len(rows), int(rows[0]["id"]))
        first_bad: int | None = None
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
            rid = int(r["id"])
            canon = str(r["canonical_payload_text"] or "").encode("utf-8")

            if prev_stored != prev_link:
                msg = (
                    f"row id={rid}: prev_chain_hash bricht Kette "
                    f"(erwartet {prev_link.hex()[:12]}.., "
                    f"gespeichert {prev_stored.hex() if isinstance(prev_stored, (bytes, memoryview)) else prev_stored})"
                )
                errors.append(msg)
                first_bad = first_bad or rid
            recomputed = ledger_chain_digest(prev_stored, canon)
            if recomputed != ch_stored:
                msg = f"row id={rid}: chain_hash Rekonstruktion mismatch (Payload/Spec)"
                errors.append(msg)
                first_bad = first_bad or rid
            if not ed25519_verify(pub, sig, ch_stored):
                msg = f"row id={rid}: Ed25519-Signatur ungueltig"
                errors.append(msg)
                first_bad = first_bad or rid
            prev_link = ch_stored

        return (not bool(errors), errors, len(rows), first_bad)

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
