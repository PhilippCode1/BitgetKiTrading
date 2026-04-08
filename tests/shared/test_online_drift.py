from shared_py.online_drift import (
    action_rank,
    merge_online_drift_actions,
    normalize_online_drift_action,
)


def test_merge_online_drift_actions_picks_strongest() -> None:
    assert merge_online_drift_actions("ok", "warn") == "warn"
    assert merge_online_drift_actions("warn", "shadow_only") == "shadow_only"
    assert merge_online_drift_actions("shadow_only", "hard_block") == "hard_block"
    assert merge_online_drift_actions(None, "", "ok") == "ok"


def test_action_rank_order() -> None:
    assert action_rank("ok") < action_rank("warn")
    assert action_rank("warn") < action_rank("shadow_only")
    assert action_rank("shadow_only") < action_rank("hard_block")


def test_normalize_unknown_defaults_ok() -> None:
    assert normalize_online_drift_action("nope") == "ok"
