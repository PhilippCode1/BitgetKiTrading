"""Prompt 72: bei Redis-Ausfall vor Shadow-Read: Fail-Closed + in-process Halt."""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO = Path(__file__).resolve().parents[3]
LB = REPO / "services" / "live-broker" / "src"
if str(LB) not in sys.path:
    sys.path.insert(0, str(LB))

from live_broker.config import LiveBrokerSettings  # noqa: E402
from live_broker.exceptions import GlobalHaltException, ShadowDivergenceError  # noqa: E402
from live_broker.global_halt_latch import GlobalHaltLatch  # noqa: E402
from live_broker.orders.models import OrderCreateRequest  # noqa: E402
from live_broker.orders.service import LiveBrokerOrderService  # noqa: E402


def test_get_shadow_unavailable_activates_latch_and_raises(  # noqa: D103
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dsn = "postgresql://t:t@127.0.0.1:1/db"
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("DATABASE_URL", dsn)
    monkeypatch.setenv("LIVE_BROKER_REQUIRE_COMMERCIAL_GATES", "false")
    s = LiveBrokerSettings()
    s2 = s.model_copy(
        update={
            "require_shadow_match_before_live": True,
            "live_require_execution_binding": True,
            "live_require_operator_release_for_live_open": False,
        }
    )
    eid = uuid.uuid4()
    latch = GlobalHaltLatch("redis://127.0.0.1:6379/0")
    with patch(
        "live_broker.orders.service.get_shadow_match_latch_read_status",
        return_value="redis_unavailable",
    ):
        with patch(
            "live_broker.orders.service.try_publish_global_halt_state",
            return_value=False,
        ) as pubm:
            ex = MagicMock()
            repo = MagicMock()
            repo.get_execution_decision = MagicMock(
                return_value={
                    "decision_action": "live_candidate_recorded",
                    "symbol": "BTCUSDT",
                }
            )
            req = OrderCreateRequest(
                symbol="BTCUSDT",
                side="buy",
                size="0.01",
                order_type="market",
                source_execution_decision_id=eid,
            )
            svc = LiveBrokerOrderService(
                s2, repo, ex, bus=None, global_halt=latch
            )
            with pytest.raises(ShadowDivergenceError) as e:
                svc._assert_live_open_governance(  # noqa: SLF001
                    req,
                    opening_order=True,
                    allow_safety_bypass=False,
                )
            assert "shadow_match_redis_unavailable" in (e.value.reason or "")
            assert pubm.call_count == 1
    assert latch.is_halted is True
    with pytest.raises(GlobalHaltException):
        latch.assert_not_halted()
