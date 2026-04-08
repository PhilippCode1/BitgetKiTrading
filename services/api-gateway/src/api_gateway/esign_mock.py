"""Mock E-Sign-Adapter + Webhook-HMAC (Prompt 12, austauschbar gegen echten Provider)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class MockEnvelopePayload(BaseModel):
    """Payload fuer Kunden-UI (Signatur-URL ist hier nur Platzhalter)."""

    envelope_id: str = Field(..., description="Eindeutige Envelope-ID (Mock)")
    signing_url: str = Field(..., description="URL zum Signieren (Mock: Dashboard-Link)")
    expires_at_unix: int = Field(..., description="Ablaufzeit (Unix-Sekunden)")


def create_mock_envelope(
    *,
    contract_id: str,
    tenant_id: str,
    ttl_seconds: int = 3600,
) -> MockEnvelopePayload:
    eid = str(uuid.uuid4())
    # Frontend oeffnet dieselbe Vertragsseite; echter Provider wuerde externe URL liefern.
    signing_url = f"/account/contract?envelope={eid}&contract={contract_id}"
    return MockEnvelopePayload(
        envelope_id=eid,
        signing_url=signing_url,
        expires_at_unix=int(time.time()) + int(ttl_seconds),
    )


def build_webhook_body(
    *,
    contract_id: str,
    tenant_id: str,
    envelope_id: str,
    event: str = "completed",
) -> dict[str, Any]:
    return {
        "provider": "mock",
        "event": event,
        "contract_id": contract_id,
        "tenant_id": tenant_id,
        "envelope_id": envelope_id,
        "completed_at_unix": int(time.time()),
    }


def sign_webhook_body(secret: str, body: dict[str, Any]) -> str:
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()


def verify_webhook_signature(secret: str, body_bytes: bytes, signature_hex: str) -> bool:
    if not secret or not signature_hex:
        return False
    expected = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_hex.lower())
