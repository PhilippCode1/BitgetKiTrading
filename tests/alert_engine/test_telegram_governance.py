from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
ALERT_ENGINE_SRC = ROOT / "services" / "alert-engine" / "src"
for candidate in (ROOT / "shared" / "python" / "src", ALERT_ENGINE_SRC):
    s = str(candidate)
    if s not in sys.path:
        sys.path.insert(0, s)

from alert_engine.telegram.governance import manual_confirm_token_verify, operator_user_allowed


def test_operator_user_allowed_empty_allowlist() -> None:
    ok, scope = operator_user_allowed(user_id=1, allowed_ids=set())
    assert ok and scope == "rbac_disabled_allow_all"


def test_operator_user_allowed_rejects_unknown_user() -> None:
    ok, scope = operator_user_allowed(user_id=99, allowed_ids={1, 2})
    assert not ok and scope == "rejected_rbac_user_not_in_allowlist"


def test_operator_user_allowed_rejects_missing_user() -> None:
    ok, scope = operator_user_allowed(user_id=None, allowed_ids={1})
    assert not ok and scope == "rejected_rbac_telegram_user_unknown"


def test_manual_token_skipped_when_unconfigured() -> None:
    ok, fp = manual_confirm_token_verify(configured_token="", parts=["a", "b"])
    assert ok and fp is None


def test_manual_token_requires_third_part() -> None:
    ok, fp = manual_confirm_token_verify(configured_token="secret", parts=["p", "c"])
    assert not ok and fp is None


def test_manual_token_constant_time_match() -> None:
    ok, fp = manual_confirm_token_verify(configured_token="tok", parts=["p", "c", "tok"])
    assert ok and fp and len(fp) == 32


def test_manual_token_rejects_wrong() -> None:
    ok, fp = manual_confirm_token_verify(configured_token="tok", parts=["p", "c", "nope"])
    assert not ok and fp is None
