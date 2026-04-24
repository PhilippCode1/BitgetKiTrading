"""
Gemeinsame Typen fuer rc_health_edge / rc_health_runner.
"""

from __future__ import annotations


class RcHealthFailure(Exception):
    """Eindeutig nachvollziehbarer Fehler (Exit 1) mit service_id für CI/Audit."""

    def __init__(
        self, service_id: str, service_name: str, message: str, *, hint: str = ""
    ) -> None:
        self.service_id = service_id
        self.service_name = service_name
        self.message = message
        self.hint = hint
        super().__init__(f"[{service_id}] {service_name}: {message}")


def format_exit_one_line(f: RcHealthFailure) -> str:
    """Eine Zeile: welcher Service — fuer stderr/CI."""
    h = f" | hint={f.hint}" if f.hint else ""
    return f"FEHLER service_id={f.service_id} service_name={f.service_name!r} | {f.message}{h}"


def classify_connection_refused_oserror(exc: OSError) -> str:
    """Unterscheidet typische Windows/Linux „connection refused”-Fälle."""
    s = str(exc)
    w = getattr(exc, "winerror", None)
    errno = getattr(exc, "errno", None) or 0
    is_refused = w == 10061 or "10061" in s or errno in (10061, 61, 111) or "refused" in s.lower()
    if not is_refused:
        return s
    return (
        s
        + " | Diagnose: TCP-Verbindung abgelehnt. "
        "Falls `docker compose ps` den Container (z.B. api-gateway) nicht zeigt oder „Exit“: "
        "Stack/Container starten (Docker-Ebene). "
        "Falls der Container **läuft**, lauscht der Prozess im Container evtl. noch nicht "
        "(App-Boot) — `RC_HEALTH_STARTUP_BUDGET_SEC` / `--startup-budget-sec` erhoehen oder warten. "
        "Zieladresse/Port: siehe `API_GATEWAY_URL` (typisch :8000)."
    )
