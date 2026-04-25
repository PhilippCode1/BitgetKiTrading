"""Health-Landkarte fuer die Main Console (deutsch, fail-closed)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

Status = Literal["ok", "warn", "fail", "unknown"]
FreshnessStatus = Literal["fresh", "stale", "missing", "not_applicable"]

_STATUS_ORDER = {"fail": 0, "unknown": 1, "warn": 2, "ok": 3}


@dataclass(frozen=True)
class HealthMapComponent:
    name: str
    status: Status
    freshness_status: FreshnessStatus
    live_auswirkung_de: str
    blockiert_live: bool
    letzter_erfolg_ts: str | None
    letzter_fehler_ts: str | None
    fehlergrund_de: str
    nächster_schritt_de: str


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def redact_health_details(value: Any) -> str:
    raw = str(value) if value is not None else ""
    raw = re.sub(
        r"(?i)(apikey|api_key|secret|password|passphrase|token|authorization)\s*[:=]\s*\S+",
        r"\1=***REDACTED***",
        raw,
    )
    raw = re.sub(r"(?i)bearer\s+\S+", "Bearer ***REDACTED***", raw)
    return raw[:2000] + ("…" if len(raw) > 2000 else "")


def normalize_status(raw: str | None) -> Status:
    if not raw:
        return "unknown"
    val = str(raw).strip().lower()
    if val in ("ok", "warn", "fail", "unknown"):
        return val  # type: ignore[return-value]
    return "unknown"


def normalize_freshness(raw: str | None) -> FreshnessStatus:
    if not raw:
        return "missing"
    val = str(raw).strip().lower()
    if val in ("fresh", "stale", "missing", "not_applicable"):
        return val  # type: ignore[return-value]
    return "missing"


def component_payload(component: HealthMapComponent) -> dict[str, Any]:
    return {
        "komponente": component.name,
        "status": component.status,
        "freshness_status": component.freshness_status,
        "live_auswirkung_de": component.live_auswirkung_de,
        "blockiert_live": component.blockiert_live,
        "letzter_erfolg_ts": component.letzter_erfolg_ts,
        "letzter_fehler_ts": component.letzter_fehler_ts,
        "fehlergrund_de": component.fehlergrund_de,
        "nächster_schritt_de": component.nächster_schritt_de,
    }


def evaluate_health_map(components: list[HealthMapComponent]) -> dict[str, Any]:
    """Bewertet Gesamtstatus und Live-Blocker streng fail-closed."""
    if not components:
        return {
            "gesamtstatus": "unknown",
            "live_sicher": False,
            "live_blockiert": True,
            "blocker_gründe_de": [
                "Keine Health-Komponenten verbunden.",
            ],
            "bewertet_ts": _now_iso(),
            "komponenten": [],
        }

    blockers: list[str] = []
    has_fail = False
    has_unknown = False
    has_warn = False

    for c in components:
        if c.status == "fail":
            has_fail = True
        elif c.status == "unknown":
            has_unknown = True
        elif c.status == "warn":
            has_warn = True

        # Harte Regeln (fail-closed)
        if c.blockiert_live:
            blockers.append(f"{c.name}: {c.live_auswirkung_de}")
        if c.name in {"Market-Stream", "Signal-Engine"} and c.freshness_status in {"stale", "missing"}:
            blockers.append(f"{c.name}: Daten nicht frisch fuer Live-Entscheidungen.")
        if c.name == "Reconcile" and c.freshness_status in {"stale", "missing"}:
            blockers.append("Reconcile: stale/missing blockiert Live-Openings.")
        if c.name == "Redis/Eventbus" and c.status in {"fail", "unknown"}:
            blockers.append("Redis/Eventbus: Shadow-Match/Liquidity/Signals nicht verlässlich.")
        if c.name == "Postgres" and c.status in {"fail", "unknown"}:
            blockers.append("Postgres: livekritische Pfade ohne DB-Wahrheit.")
        if c.name in {"Live-Broker", "Reconcile"} and c.status == "unknown":
            blockers.append(f"{c.name}: unknown im livekritischen Pfad.")

    live_blockiert = len(blockers) > 0

    if has_fail:
        gesamtstatus: Status = "fail"
    elif has_unknown:
        gesamtstatus = "unknown"
    elif has_warn:
        gesamtstatus = "warn"
    else:
        gesamtstatus = "ok"

    return {
        "gesamtstatus": gesamtstatus,
        "live_sicher": (not live_blockiert) and gesamtstatus == "ok",
        "live_blockiert": live_blockiert,
        "blocker_gründe_de": blockers,
        "bewertet_ts": _now_iso(),
        "komponenten": [component_payload(c) for c in sorted(components, key=lambda x: _STATUS_ORDER[x.status])],
    }


def assert_no_commercial_terms(text: str) -> None:
    lowered = text.lower()
    for token in ("billing", "kunde", "kunden", "abo", "subscription", "saas", "payment"):
        if token in lowered:
            raise ValueError(f"verbotener_begriff:{token}")
