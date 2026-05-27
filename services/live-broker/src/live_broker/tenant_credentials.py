"""Tenant-scoped Bitget-Credentials fuer private REST (ContextVar, fail-closed)."""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from shared_py.tenant_exchange_credentials import (
    BitgetCredentialBundle,
    resolve_bitget_credentials_for_tenant,
)

from live_broker.tenant_gate import gate_tenant_from_intent

if TYPE_CHECKING:
    from live_broker.config import LiveBrokerSettings

_active_tenant_credentials: ContextVar[BitgetCredentialBundle | None] = ContextVar(
    "live_broker_active_tenant_credentials",
    default=None,
)


def get_active_tenant_credentials() -> BitgetCredentialBundle | None:
    return _active_tenant_credentials.get()


def tenant_credentials_required_from_env() -> bool:
    return os.environ.get(
        "TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT", ""
    ).strip().lower() in ("true", "1", "yes")


def resolve_bundle_for_trace(
    settings: LiveBrokerSettings,
    trace: Mapping[str, Any] | None,
) -> BitgetCredentialBundle | None:
    tid = gate_tenant_from_intent(
        config_tenant_id=settings.modul_mate_gate_tenant_id,
        trace=trace,
    )
    return resolve_bitget_credentials_for_tenant(tid)


@contextmanager
def tenant_credentials_scope(
    settings: LiveBrokerSettings,
    trace: Mapping[str, Any] | None,
) -> Iterator[BitgetCredentialBundle | None]:
    """
    Aktiviert Mandanten-Credentials fuer nachfolgende BitgetPrivateRestClient-Aufrufe
    im selben Task/Thread.
    """
    from live_broker.private_rest import BitgetRestError

    bundle = resolve_bundle_for_trace(settings, trace)
    if tenant_credentials_required_from_env() and bundle is None:
        raise BitgetRestError(
            classification="auth",
            message="tenant_exchange_credentials_unavailable",
            retryable=False,
        )
    token = _active_tenant_credentials.set(bundle)
    try:
        yield bundle
    finally:
        _active_tenant_credentials.reset(token)
