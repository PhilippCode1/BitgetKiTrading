"""Live broker service with shadow intake, reconcile and health."""

from fastapi import FastAPI

from live_broker.config import LiveBrokerSettings


def create_app(*, start_background: bool = True) -> FastAPI:
    from live_broker.app import create_app as _create_app

    return _create_app(start_background=start_background)


__all__ = ["LiveBrokerSettings", "create_app"]
