from shared_py.audit_ledger_chain import GENESIS_CHAIN_HASH, ledger_chain_digest


def test_golden_vector_matches_rust_apex_audit_ledger() -> None:
    prev = GENESIS_CHAIN_HASH
    canon = b'{"a":1}'
    d = ledger_chain_digest(prev, canon)
    assert d.hex() == "b06a229070741292512e8760f470dd7a4c46ccfdf253df781d88dabe58c1ccb1"
