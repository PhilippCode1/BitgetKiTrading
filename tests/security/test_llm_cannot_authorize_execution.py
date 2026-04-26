from __future__ import annotations

from shared_py.strategy_asset_evidence import llm_strategy_execution_authority_contract


def test_llm_execution_authority_must_be_none() -> None:
    assert llm_strategy_execution_authority_contract({"execution_authority": "none"}) == []
    assert "execution_authority_muss_none_sein" in llm_strategy_execution_authority_contract(
        {"execution_authority": "allow_live"}
    )
