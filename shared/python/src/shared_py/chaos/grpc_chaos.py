"""
gRPC-aio: Client-Interceptor fuer kuenstliche Latenz (z. B. jeder 10. Aufruf, > 5s Deadline).
"""

from __future__ import annotations

import asyncio
from typing import Any, TypeVar

import grpc.aio
from grpc.aio import UnaryUnaryClientInterceptor

RequestT = TypeVar("RequestT")


def build_timesfm_chaos_interceptors(
    *,
    every_n: int,
    delay_sec: float,
) -> list[UnaryUnaryClientInterceptor]:
    """
    Baut einen ``UnaryUnaryClientInterceptor``, der bei jedem ``every_n``-ten RPC
    ``asyncio.sleep(delay_sec)`` **vor** dem eigentlichen Call ausfuehrt.
    """
    n = int(every_n)
    if n <= 0 or delay_sec <= 0:
        return []

    class _ChaosInterceptor(UnaryUnaryClientInterceptor):
        def __init__(self) -> None:
            self._c = 0

        async def intercept_unary_unary(
            self,
            continuation: Any,
            client_call_details: Any,
            request: RequestT,
        ) -> Any:
            self._c += 1
            if self._c % n == 0:
                await asyncio.sleep(float(delay_sec))
            return await continuation(client_call_details, request)

    return [_ChaosInterceptor()]
