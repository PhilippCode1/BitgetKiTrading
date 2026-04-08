"""Live broker service with shadow intake, reconcile and health."""

from live_broker.config import LiveBrokerSettings


def create_app(*args, **kwargs):
    from live_broker.app import create_app as _create_app

    return _create_app(*args, **kwargs)


__all__ = ["LiveBrokerSettings", "create_app"]
