from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
SHARED = REPO / "shared" / "python" / "src"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from shared_py.shadow_live_divergence import (  # noqa: E402
    parse_prebound_execution_id,
    shadow_match_latch_redis_key,
)


def test_shadow_match_latch_key_format() -> None:
    u = str(uuid4())
    assert shadow_match_latch_redis_key(u) == f"shadow:match:{u}"


def test_parse_prebound_from_nested_signal() -> None:
    eid = str(uuid4())
    out = parse_prebound_execution_id(
        signal_payload={"foo": 1},
        payload={"execution_id": eid},
        trace={},
    )
    assert out == eid
