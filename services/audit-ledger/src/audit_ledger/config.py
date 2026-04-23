from __future__ import annotations

import hashlib
from typing import ClassVar

from config.settings import BaseServiceSettings
from pydantic import Field, field_validator, model_validator
from pydantic_settings import SettingsConfigDict


class AuditLedgerSettings(BaseServiceSettings):
    """Settings fuer audit-ledger (ENV via pydantic-settings)."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    production_required_fields: ClassVar[tuple[str, ...]] = (
        BaseServiceSettings.production_required_fields + ("database_url",)
    )

    audit_ledger_port: int = Field(default=8098, alias="AUDIT_LEDGER_PORT")
    apex_audit_ledger_ed25519_seed_hex: str = Field(
        default="",
        alias="APEX_AUDIT_LEDGER_ED25519_SEED_HEX",
        description="64 Hex-Zeichen (32 Byte) Ed25519-Seed; in Produktion aus Vault/HSM injiziert.",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("audit_ledger_port")
    @classmethod
    def _port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError("AUDIT_LEDGER_PORT ungueltig")
        return v

    @model_validator(mode="after")
    def _seed_or_dev(self) -> AuditLedgerSettings:
        hx = self.apex_audit_ledger_ed25519_seed_hex.strip()
        if hx:
            if len(hx) != 64:
                raise ValueError("APEX_AUDIT_LEDGER_ED25519_SEED_HEX muss 64 Hex-Zeichen sein")
            try:
                bytes.fromhex(hx)
            except ValueError as exc:
                raise ValueError("APEX_AUDIT_LEDGER_ED25519_SEED_HEX ungueltig") from exc
            return self
        if self.production or self.app_env in ("shadow", "production"):
            raise ValueError(
                "APEX_AUDIT_LEDGER_ED25519_SEED_HEX ist fuer Produktion/Shadow Pflicht"
            )
        return self

    def ed25519_seed_32(self) -> bytes:
        hx = self.apex_audit_ledger_ed25519_seed_hex.strip()
        if hx:
            return bytes.fromhex(hx)
        return hashlib.sha256(b"apex-audit-ledger-local-dev-v1-INSECURE").digest()
