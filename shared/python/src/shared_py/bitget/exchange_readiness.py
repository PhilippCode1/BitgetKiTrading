from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ReadinessVerdict = Literal["PASS", "PASS_WITH_WARNINGS", "FAIL"]
PermissionVerdict = Literal["ok", "warning", "blocker"]

READINESS_CONTRACT_VERSION = "bitget-exchange-readiness-v1"
MAX_SERVER_TIME_SKEW_MS = 5_000
WRITE_ORDER_ALLOWED_DEFAULT = False
READONLY_SAFE_METHODS = frozenset({"GET"})
FORBIDDEN_READINESS_ACTIONS = frozenset(
    {
        "cancel",
        "cancel-order",
        "place-order",
        "replace",
        "submit",
        "submit-order",
        "trade",
    }
)


@dataclass(frozen=True)
class PermissionAssessment:
    status: PermissionVerdict
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def readiness_verdict(blockers: list[str], warnings: list[str]) -> ReadinessVerdict:
    if blockers:
        return "FAIL"
    if warnings:
        return "PASS_WITH_WARNINGS"
    return "PASS"


def assess_permissions(permissions: dict[str, Any] | None) -> PermissionAssessment:
    """Assess Bitget key permissions without assuming API-specific field names."""
    if not permissions:
        return PermissionAssessment(
            status="warning",
            warnings=["permission_evidence_missing_live_write_blocked"],
        )
    blockers: list[str] = []
    warnings: list[str] = []
    normalized = {str(k).lower(): v for k, v in permissions.items()}

    def truthy(name: str) -> bool:
        value = normalized.get(name)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled", "allow"}

    withdrawal_keys = (
        "withdraw",
        "withdrawal",
        "withdraw_permission",
        "withdrawpermission",
        "can_withdraw",
    )
    if any(truthy(key) for key in withdrawal_keys):
        blockers.append("withdrawal_permission_present")

    trading_known = any(
        key in normalized
        for key in (
            "trade",
            "trading",
            "can_trade",
            "order",
            "order_permission",
            "trade_permission",
        )
    )
    if not trading_known:
        warnings.append("trading_permission_unknown_live_write_blocked")

    if blockers:
        return PermissionAssessment(status="blocker", blockers=blockers, warnings=warnings)
    if warnings:
        return PermissionAssessment(status="warning", warnings=warnings)
    return PermissionAssessment(status="ok")


def server_time_skew_blockers(offset_ms: int | None, *, max_skew_ms: int = MAX_SERVER_TIME_SKEW_MS) -> list[str]:
    if offset_ms is None:
        return ["server_time_skew_unknown"]
    if abs(int(offset_ms)) > max_skew_ms:
        return [f"server_time_skew_exceeds_budget:{offset_ms}ms>{max_skew_ms}ms"]
    return []


def classify_http_status(status_code: int | None) -> str:
    if status_code is None:
        return "not_checked"
    if status_code == 401:
        return "auth"
    if status_code == 403:
        return "permission"
    if status_code == 429:
        return "rate_limit"
    if 500 <= status_code <= 599:
        return "server"
    if 400 <= status_code <= 499:
        return "client"
    return "ok"


def path_uses_legacy_v1(path: str) -> bool:
    return "/api/v1/" in path or path.startswith("/api/v1/")


def assert_readonly_request(method: str, path: str) -> None:
    if method.upper() not in READONLY_SAFE_METHODS:
        raise ValueError(f"readiness request must be read-only: {method} {path}")
    lowered = path.lower()
    if any(action in lowered for action in FORBIDDEN_READINESS_ACTIONS):
        raise ValueError(f"readiness path is write-like and forbidden: {path}")
