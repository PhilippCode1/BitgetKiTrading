from __future__ import annotations

from monitor_engine.alerts.dedupe import PublishDedupe


def test_publish_dedupe_blocks_within_window() -> None:
    d = PublishDedupe()
    assert d.allow_publish("k1", dedupe_sec=10) is True
    assert d.allow_publish("k1", dedupe_sec=10) is False


def test_publish_dedupe_different_keys() -> None:
    d = PublishDedupe()
    assert d.allow_publish("a", dedupe_sec=60) is True
    assert d.allow_publish("b", dedupe_sec=60) is True
