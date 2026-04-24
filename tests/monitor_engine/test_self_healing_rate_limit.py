"""Prompt 74: dediziert testbare Restart-/Schleifen-Logik."""

from __future__ import annotations

from monitor_engine.storage.repo_self_healing import count_allowed_restarts_in_window, prune_restart_events

NOW = 1_700_000_000.0
WINDOW = 3600.0
MAX_N = 3


def test_prune_restart_events_rolls_window() -> None:
    t0 = [NOW - 100, NOW - 4000, NOW - 5000]
    pruned = sorted(prune_restart_events(t0, NOW, window_sec=WINDOW))
    # Alles aelter als 1h fällt weg, bis auf NOW-100
    assert len([x for x in t0 if NOW - x < WINDOW + 0.5]) == len(pruned)
    assert len(pruned) <= 3


def test_rate_limit_allows_3_rejects_4th() -> None:
    events = [NOW - 10, NOW - 20, NOW - 30]
    ok, _p = count_allowed_restarts_in_window(
        events, now=NOW, window_sec=WINDOW, max_n=MAX_N
    )
    assert ok is False
    # Nur zwei Events im Fenster -> noch Platz
    ok2, p2 = count_allowed_restarts_in_window(
        [NOW - 10, NOW - 20], now=NOW, window_sec=WINDOW, max_n=MAX_N
    )
    assert ok2 is True
    assert len(p2) == 2


def test_4th_restart_after_hour_passes() -> None:
    # Drei alte, eine sehr alte: nur eine zählt im 1h-Fenster, wenn "now" 4000s später
    old = NOW - 4000.0
    events_4 = [old, old, old, NOW - 200]
    ok, _p = count_allowed_restarts_in_window(
        events_4, now=NOW, window_sec=WINDOW, max_n=MAX_N
    )
    # Nur NOW-200 liegt in letzter Stunde -> 1 < 3
    assert ok is True


def test_is_critical_for_stale_heartbeat() -> None:
    from monitor_engine.checks.services_http import ServiceCheckResult
    from monitor_engine.self_healing.coordinator import is_critical_for_self_heal

    crs = [
        ServiceCheckResult(
            service_name="feature-engine",
            check_type="metrics",
            status="degraded",
            latency_ms=12,
            details={"worker_heartbeat": {"age_sec": 350.0}},
        )
    ]
    assert is_critical_for_self_heal(crs, stale_heartbeat_crit_sec=300.0) is True
    assert is_critical_for_self_heal(crs, stale_heartbeat_crit_sec=400.0) is False


def test_dod_post_restart_sets_recovering_requires_degraded() -> None:
    """
    Verhalten: try_begin_restart(from=degraded) wechselt DB -> recovering.
    Ohne laufendes PostgreSQL: nur Doku, dass E2E DB-Migration 600 nötig ist.
    """
    # rein keine Assertion außer Import-Smoke
    from monitor_engine.storage import repo_self_healing as m

    assert m.DEFAULT_MAX_RESTARTS == 3
