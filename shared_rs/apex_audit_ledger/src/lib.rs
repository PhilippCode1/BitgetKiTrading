//! Kryptographische Verkettung: `chain_hash = SHA256(prev_chain_hash || canonical_payload_utf8)`.
//! Muss byte-identisch zur Python-Implementierung in `shared_py.audit_ledger_chain` sein.

use sha2::{Digest, Sha256};

/// 32-Byte-Genesis (leere Kette / erster Block).
pub const GENESIS_CHAIN_HASH: [u8; 32] = [0u8; 32];

/// SHA256(prev || payload_utf8_bytes).
#[must_use]
pub fn ledger_chain_digest(prev_chain_hash: &[u8; 32], canonical_payload_utf8: &[u8]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev_chain_hash.as_slice());
    h.update(canonical_payload_utf8);
    h.finalize().into()
}

#[cfg(test)]
mod tests {
    use super::*;
    use hex::encode;

    #[test]
    fn golden_matches_python_reference() {
        let prev = GENESIS_CHAIN_HASH;
        let canon = br#"{"a":1}"#;
        let d = ledger_chain_digest(&prev, canon);
        assert_eq!(
            encode(d),
            "b06a229070741292512e8760f470dd7a4c46ccfdf253df781d88dabe58c1ccb1"
        );
    }
}
