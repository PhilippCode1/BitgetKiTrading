from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
API_GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"
for candidate in (REPO_ROOT, API_GATEWAY_SRC):
    s = str(candidate)
    if s not in sys.path:
        sys.path.insert(0, s)


def test_llm_token_line_total_is_linear_no_hidden_multiplier() -> None:
    from api_gateway.commerce.pricing import llm_tokens_line_total_usd

    p = Decimal("0.002")
    assert llm_tokens_line_total_usd(token_count=1000, usd_per_1k_tokens=p) == Decimal("0.002")
    assert llm_tokens_line_total_usd(token_count=500, usd_per_1k_tokens=p) == Decimal("0.001")
