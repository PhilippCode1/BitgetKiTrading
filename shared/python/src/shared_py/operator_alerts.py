"""Deutsche Operator-Alerts: Priorisierung P0–P3, Live-Block-Flags, Redaction."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

Severity = Literal["P0", "P1", "P2", "P3"]

_SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


@dataclass(frozen=True)
class OperatorAlert:
    titel_de: str
    beschreibung_de: str
    severity: Severity
    live_blockiert: bool
    betroffene_komponente: str
    betroffene_assets: list[str]
    empfohlene_aktion_de: str
    nächster_sicherer_schritt_de: str
    technische_details_redacted: str
    zeitpunkt: str
    korrelation_id: str
    aktiv: bool = True


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def redact_technical_details(value: Any) -> str:
    """Entfernt secret-ähnliche Muster aus Freitext/JSON-ähnlichen Strings."""
    raw = str(value) if value is not None else ""
    lowered = raw.lower()
    for token in (
        "api_key",
        "apikey",
        "secret",
        "password",
        "passphrase",
        "token",
        "authorization",
        "bearer ",
    ):
        if token in lowered:
            raw = re.sub(
                rf"(?i)({re.escape(token)}[^\s\"']*)(\s*[:=]\s*)(\S+)",
                r"\1\2***REDACTED***",
                raw,
            )
    if len(raw) > 2000:
        raw = raw[:2000] + "…"
    return raw


def normalize_severity(raw: str | None) -> Severity:
    if not raw:
        return "P1"
    s = str(raw).strip().upper()
    if s in ("P0", "P1", "P2", "P3"):
        return s  # type: ignore[return-value]
    return "P1"


def alert_from_reconcile_fail(*, detail: str | None = None) -> OperatorAlert:
    rid = str(uuid.uuid4())
    return OperatorAlert(
        titel_de="Reconcile fehlgeschlagen",
        beschreibung_de=(
            "Der letzte Reconcile-Lauf meldet Fehler. Lokale Wahrheit und Exchange "
            "stimmen möglicherweise nicht überein."
        ),
        severity="P0",
        live_blockiert=True,
        betroffene_komponente="live-broker / reconcile",
        betroffene_assets=[],
        empfohlene_aktion_de="Reconcile-Logs prüfen, Drift analysieren, keine neuen Live-Openings.",
        nächster_sicherer_schritt_de="Safety-Latch-Status prüfen und Reconcile erneut ausführen.",
        technische_details_redacted=redact_technical_details(detail or ""),
        zeitpunkt=_now_iso(),
        korrelation_id=rid,
        aktiv=True,
    )


def alert_from_exchange_truth_missing(*, detail: str | None = None) -> OperatorAlert:
    rid = str(uuid.uuid4())
    return OperatorAlert(
        titel_de="Exchange-Truth fehlt oder ist unklar",
        beschreibung_de="Upstream- oder Private-API-Status ist nicht ausreichend für sichere Live-Entscheidungen.",
        severity="P0",
        live_blockiert=True,
        betroffene_komponente="live-broker / exchange",
        betroffene_assets=[],
        empfohlene_aktion_de="Bitget-Erreichbarkeit und private Auth prüfen.",
        nächster_sicherer_schritt_de="Read-only Diagnose, dann Reconcile abwarten.",
        technische_details_redacted=redact_technical_details(detail or ""),
        zeitpunkt=_now_iso(),
        korrelation_id=rid,
        aktiv=True,
    )


def alert_from_kill_switch_active(*, count: int = 1) -> OperatorAlert:
    rid = str(uuid.uuid4())
    return OperatorAlert(
        titel_de="Kill-Switch aktiv",
        beschreibung_de=f"Es sind {count} aktive Kill-Switch-Ereignis(se) gemeldet.",
        severity="P0",
        live_blockiert=True,
        betroffene_komponente="live-broker / kill-switch",
        betroffene_assets=[],
        empfohlene_aktion_de="Ursache klären, normale Orders stoppen, nur Safety-Pfade nutzen.",
        nächster_sicherer_schritt_de="Nach Analyse Release nur mit dokumentiertem Audit.",
        technische_details_redacted="",
        zeitpunkt=_now_iso(),
        korrelation_id=rid,
        aktiv=True,
    )


def alert_from_safety_latch_active() -> OperatorAlert:
    rid = str(uuid.uuid4())
    return OperatorAlert(
        titel_de="Safety-Latch aktiv",
        beschreibung_de="Die Plattform hat die automatische Live-Execution angehalten (Safety-Latch).",
        severity="P0",
        live_blockiert=True,
        betroffene_komponente="live-broker / safety-latch",
        betroffene_assets=[],
        empfohlene_aktion_de="Reconcile und Audit prüfen, Ursache beheben.",
        nächster_sicherer_schritt_de="Explizites Latch-Release nur nach Freigabe und Dokumentation.",
        technische_details_redacted="",
        zeitpunkt=_now_iso(),
        korrelation_id=rid,
        aktiv=True,
    )


def alert_from_bitget_private_auth_error(*, detail: str | None = None) -> OperatorAlert:
    rid = str(uuid.uuid4())
    return OperatorAlert(
        titel_de="Bitget private API: Authentifizierung fehlgeschlagen",
        beschreibung_de="Private Bitget-Authentifizierung ist fehlgeschlagen oder unklar.",
        severity="P0",
        live_blockiert=True,
        betroffene_komponente="live-broker / bitget-private",
        betroffene_assets=[],
        empfohlene_aktion_de="Schlüsselrechte und Signatur prüfen (ohne Secrets in Logs).",
        nächster_sicherer_schritt_de="Read-only Readiness erneut ausführen, dann Reconcile.",
        technische_details_redacted=redact_technical_details(detail or ""),
        zeitpunkt=_now_iso(),
        korrelation_id=rid,
        aktiv=True,
    )


def alert_from_redis_or_db_live_critical(*, component: str, detail: str | None = None) -> OperatorAlert:
    rid = str(uuid.uuid4())
    return OperatorAlert(
        titel_de="Redis oder Datenbank im livekritischen Pfad ausgefallen",
        beschreibung_de=f"Komponente {component} ist für Live-Trading kritisch und nicht verfügbar.",
        severity="P0",
        live_blockiert=True,
        betroffene_komponente=component,
        betroffene_assets=[],
        empfohlene_aktion_de="Dienststatus und Verbindung prüfen, keine Live-Submits.",
        nächster_sicherer_schritt_de="Wiederherstellung laut Runbook, dann Health erneut prüfen.",
        technische_details_redacted=redact_technical_details(detail or ""),
        zeitpunkt=_now_iso(),
        korrelation_id=rid,
        aktiv=True,
    )


def alert_from_data_quality_fail(*, assets: list[str]) -> OperatorAlert:
    rid = str(uuid.uuid4())
    return OperatorAlert(
        titel_de="Datenqualität FAIL für livefähiges Asset",
        beschreibung_de="Marktdaten oder Qualitätsgates melden FAIL für ein als livefähig eingestuftes Asset.",
        severity="P0",
        live_blockiert=True,
        betroffene_komponente="market-data / signal-engine",
        betroffene_assets=list(assets),
        empfohlene_aktion_de="Asset-Datenquelle und Gates prüfen.",
        nächster_sicherer_schritt_de="Asset in Quarantäne oder Shadow bis Daten wieder grün.",
        technische_details_redacted="",
        zeitpunkt=_now_iso(),
        korrelation_id=rid,
        aktiv=True,
    )


def alert_from_liquidity_guard_no_orderbook(*, symbol: str | None = None) -> OperatorAlert:
    rid = str(uuid.uuid4())
    assets = [symbol] if symbol else []
    return OperatorAlert(
        titel_de="Liquiditäts-Guard: Orderbuch fehlt",
        beschreibung_de="Für die geplante Ausführung fehlt ein frisches Orderbuch.",
        severity="P0",
        live_blockiert=True,
        betroffene_komponente="live-broker / liquidity-guard",
        betroffene_assets=assets,
        empfohlene_aktion_de="Orderbuch-Stream und Latenz prüfen.",
        nächster_sicherer_schritt_de="Kein Live-Opening bis Orderbuch wieder valide.",
        technische_details_redacted="",
        zeitpunkt=_now_iso(),
        korrelation_id=rid,
        aktiv=True,
    )


def alert_from_unknown_order_submit(*, detail: str | None = None) -> OperatorAlert:
    rid = str(uuid.uuid4())
    return OperatorAlert(
        titel_de="Unbekannter Order-Status nach Submit",
        beschreibung_de="Der Exchange-Status nach Order-Submit ist unklar; Retry ohne Reconcile ist verboten.",
        severity="P0",
        live_blockiert=True,
        betroffene_komponente="live-broker / order-lifecycle",
        betroffene_assets=[],
        empfohlene_aktion_de="Reconcile und Order-Journal prüfen.",
        nächster_sicherer_schritt_de="Keine neuen Openings bis Klärung.",
        technische_details_redacted=redact_technical_details(detail or ""),
        zeitpunkt=_now_iso(),
        korrelation_id=rid,
        aktiv=True,
    )


def alert_from_secret_leak_suspicion(*, detail: str | None = None) -> OperatorAlert:
    rid = str(uuid.uuid4())
    return OperatorAlert(
        titel_de="Verdacht auf Secret-Leak",
        beschreibung_de="Es wurden Muster erkannt, die wie Secrets aussehen. Sofort prüfen und rotieren.",
        severity="P0",
        live_blockiert=True,
        betroffene_komponente="security / secrets",
        betroffene_assets=[],
        empfohlene_aktion_de="Quelle abstellen, Logs redigieren, Vault prüfen.",
        nächster_sicherer_schritt_de="Kein Live bis Freigabe nach Incident-Review.",
        technische_details_redacted=redact_technical_details(detail or ""),
        zeitpunkt=_now_iso(),
        korrelation_id=rid,
        aktiv=True,
    )


def alert_from_unsafe_production_env(*, detail: str | None = None) -> OperatorAlert:
    rid = str(uuid.uuid4())
    return OperatorAlert(
        titel_de="Produktion mit unsicherer Konfiguration",
        beschreibung_de="Kritische Umgebungsvariablen oder Flags wirken für Produktion riskant.",
        severity="P0",
        live_blockiert=True,
        betroffene_komponente="runtime / env",
        betroffene_assets=[],
        empfohlene_aktion_de="ENV-Profile mit Validatoren prüfen und korrigieren.",
        nächster_sicherer_schritt_de="Kein Live bis dokumentierte Freigabe.",
        technische_details_redacted=redact_technical_details(detail or ""),
        zeitpunkt=_now_iso(),
        korrelation_id=rid,
        aktiv=True,
    )


def alert_from_live_without_owner_release() -> OperatorAlert:
    rid = str(uuid.uuid4())
    return OperatorAlert(
        titel_de="Live-Flags ohne Owner-Freigabe",
        beschreibung_de="Live-Trading ist konfiguriert, aber die erforderliche Owner-/Operator-Freigabe fehlt.",
        severity="P0",
        live_blockiert=True,
        betroffene_komponente="live-broker / governance",
        betroffene_assets=[],
        empfohlene_aktion_de="Operator-Release und Evidence prüfen.",
        nächster_sicherer_schritt_de="Freigabe dokumentieren oder Live-Flags deaktivieren.",
        technische_details_redacted="",
        zeitpunkt=_now_iso(),
        korrelation_id=rid,
        aktiv=True,
    )


def alert_informational_p3(*, titel: str, beschreibung: str, component: str) -> OperatorAlert:
    rid = str(uuid.uuid4())
    return OperatorAlert(
        titel_de=titel,
        beschreibung_de=beschreibung,
        severity="P3",
        live_blockiert=False,
        betroffene_komponente=component,
        betroffene_assets=[],
        empfohlene_aktion_de="Beobachten, kein sofortiger Eingriff nötig.",
        nächster_sicherer_schritt_de="Bei Wiederholung Eskalation prüfen.",
        technische_details_redacted="",
        zeitpunkt=_now_iso(),
        korrelation_id=rid,
        aktiv=True,
    )


def sort_operator_alerts(alerts: list[OperatorAlert]) -> list[OperatorAlert]:
    """Aktive vor inaktiven; dann nach Schwere P0 zuerst."""

    def key(a: OperatorAlert) -> tuple[int, int]:
        active_rank = 0 if a.aktiv else 1
        sev = _SEVERITY_ORDER.get(a.severity, 9)
        return (active_rank, sev)

    return sorted(alerts, key=key)


def alert_payload_dict(alert: OperatorAlert) -> dict[str, Any]:
    return {
        "titel_de": alert.titel_de,
        "beschreibung_de": alert.beschreibung_de,
        "severity": alert.severity,
        "live_blockiert": alert.live_blockiert,
        "betroffene_komponente": alert.betroffene_komponente,
        "betroffene_assets": list(alert.betroffene_assets),
        "empfohlene_aktion_de": alert.empfohlene_aktion_de,
        "nächster_sicherer_schritt_de": alert.nächster_sicherer_schritt_de,
        "technische_details_redacted": alert.technische_details_redacted,
        "zeitpunkt": alert.zeitpunkt,
        "korrelation_id": alert.korrelation_id,
        "aktiv": alert.aktiv,
    }


def assert_no_forbidden_commercial_terms(text: str) -> None:
    lowered = text.lower()
    forbidden = ("kunde", "kunden", "billing", "abo", "subscription", "saas")
    for word in forbidden:
        if word in lowered:
            raise ValueError(f"verbotener_begriff:{word}")
