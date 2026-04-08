from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

logger = logging.getLogger("alert_engine.ensure_migrations")


def _repo_root() -> Path:
    # .../services/alert-engine/src/alert_engine/storage -> Eltern[5] = Repo- bzw. Image-Root (/app)
    return Path(__file__).resolve().parents[5]


def ensure_postgres_migrations_applied(database_url: str) -> int:
    """
    Nutzt infra/migrate.py (gleiche Logik wie CLI), damit alert.* u. a. vor Worker-Start existieren.
    Gibt die Anzahl in diesem Lauf neu angewendeter Dateien zurueck (0 = alles bereits angewendet).
    """
    root = _repo_root()
    mig_py = root / "infra" / "migrate.py"
    if not mig_py.is_file():
        raise RuntimeError(
            f"Migration-Runner fehlt ({mig_py}). "
            "Lokal vom Projektroot starten oder im Image infra/ mit einbinden."
        )
    spec = importlib.util.spec_from_file_location("_bitget_infra_migrate", mig_py)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Konnte migrate.py nicht laden: {mig_py}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def _migrate_log(msg: str) -> None:
        # Bereits angewendete Dateien: DEBUG (sonst 60+ Zeilen pro Container-Start)
        if msg.startswith("[migrate] skip "):
            logger.debug("%s", msg)
        else:
            logger.info("%s", msg)

    return int(mod.run_migrations(database_url.strip(), log=_migrate_log))


def count_applied_migrations(database_url: str) -> int:
    """Anzahl Eintraege in app.schema_migrations (nach erfolgreichem Lauf)."""
    import psycopg

    with psycopg.connect(database_url.strip(), connect_timeout=10) as conn:
        row = conn.execute(
            "SELECT count(*)::int FROM app.schema_migrations",
        ).fetchone()
    return int(row[0]) if row else 0
