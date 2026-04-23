from __future__ import annotations

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def ed25519_sign_chain_hash(seed_32: bytes, chain_hash_32: bytes) -> tuple[bytes, bytes]:
    """Signiert ``chain_hash_32`` (rohe SHA-256-Bytes). Rueckgabe: (signature_64, public_key_32)."""
    if len(seed_32) != 32:
        raise ValueError("Ed25519-Seed muss 32 Byte sein")
    if len(chain_hash_32) != 32:
        raise ValueError("chain_hash muss 32 Byte sein")
    sk = Ed25519PrivateKey.from_private_bytes(seed_32)
    pub = sk.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    sig = sk.sign(chain_hash_32)
    return sig, pub


def ed25519_verify(public_key_32: bytes, signature_64: bytes, message_32: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(public_key_32).verify(signature_64, message_32)
    except InvalidSignature:
        return False
    return True
