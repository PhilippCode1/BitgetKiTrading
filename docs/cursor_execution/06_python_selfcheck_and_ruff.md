# Python-Selfcheck und Ruff

Stand: 2026-04-05

## Ziel

- `tools/production_selfcheck.py` erfüllt **eigene** Ruff-/Black-Regeln und scheitert nicht an E501 o. Ä.
- Ohne `DATABASE_URL` laufen alle **vorgesehenen** Offline-Schritte durch; der DB-Block in `modul_mate_selfcheck` ist ein **SKIP**, kein Fehler.
- **Rote Zustände** bleiben erkennbar: fehlende Migration-604-Datei, fehlendes `infra/migrate.py`, nicht importierbares `shared_py`, DB-Fehler (wenn DSN gesetzt), Ruff/Black/Mypy/Pytest/Contracts/Schema/Env-Security.

## Änderungen (kurz)

| Datei                                             | Inhalt                                                                                                                                                                                                               |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tools/production_selfcheck.py`                   | E501 behoben (Zeilen umbrechen); Phasen-Ausgaben `==> …` mit `flush=True` (korrekte Log-Reihenfolge bei Pipe/CI); Exit-Code-Doku im Moduldocstring; Ruff-Pfad für `tests/unit/tools/test_selfcheck_cli_contract.py`. |
| `tools/modul_mate_selfcheck.py`                   | Prüfung, dass `infra/migrate.py` existiert; klarere OK-Zeile; lange `print`-Zeile für Ruff E501 umgebrochen.                                                                                                         |
| `tests/unit/tools/test_selfcheck_cli_contract.py` | Pytest: `modul_mate_selfcheck` ohne DB → Exit 0 + erwartete Texte; parametrisierter Ruff-Check auf die beiden Tool-Dateien.                                                                                          |

## Signale (FAIL vs. SKIP)

| Signal                         | Bedingung                                                            | Exit                      |
| ------------------------------ | -------------------------------------------------------------------- | ------------------------- |
| Migration 604 fehlt            | Datei `infra/migrations/postgres/604_modul_mate_execution_gates.sql` | 1                         |
| `migrate.py` fehlt             | `infra/migrate.py`                                                   | 1                         |
| `shared_py` nicht importierbar | Import der Gate-/Policy-Module schlägt fehl                          | 1                         |
| DB optional                    | `DATABASE_URL` leer                                                  | 0, Zeile `SKIP: …`        |
| DB mit Fehler                  | DSN gesetzt, Verbindung/Query schlägt fehl                           | 1                         |
| Kein Gate-Row                  | DSN gesetzt, kein Eintrag für Tenant                                 | 1                         |
| Ruff/Black/Mypy/Pytest/…       | wie bisher                                                           | != 0 des jeweiligen Tools |

**Hinweis:** „Pending Migrationen“ (Schema-Drift) ohne laufende DB werden nicht automatisch erkannt; die OK-Zeile weist darauf hin. Vollständiger Migrationsabgleich bleibt `infra/migrate.py` / CI-Job.

## Befehle

```bash
python tools/production_selfcheck.py
python -m ruff check tools/production_selfcheck.py tools/modul_mate_selfcheck.py
python -m pytest tests/unit/tools/test_selfcheck_cli_contract.py -q
```

## Referenz: Selfcheck-Output (Erfolg, ohne DB)

Ausführung mit `PYTHONUNBUFFERED=1` (empfohlen bei Umleitung), Auszug wie in der Konsole:

```
==> modul_mate_selfcheck (Migration 604, shared_py-Import, optional DB)
OK: Migration 604 + migrate.py vorhanden, shared_py importierbar (angewendete/pending Migrationen nur mit DB pruefbar)
SKIP: DATABASE_URL nicht gesetzt - keine DB-Pruefung
==> ruff check (Selfcheck-Pfade)
All checks passed!
==> black --check (Selfcheck-Tools + tests/shared)
==> mypy (kritische shared_py-Module, cwd shared/python)
Success: no issues found in 7 source files
==> pytest (Modul Mate / product_policy / live-broker / model_layer)
.........................                                                [100%]
25 passed in …
==> pytest tests/llm_eval
.................                                                        [100%]
17 passed in …
==> check_contracts.py
check_contracts: OK
==> check_schema.py (signals_fixture)
==> check_production_env_template_security.py
OK check_production_env_template_security: keine verbotenen Security-Flags in Vorlagen.
==> validate_env_profile (optional, aus .env.local.example)
OK validate_env_profile: local …/production_selfcheck_….env.local
OK: production_selfcheck abgeschlossen (ruff + black + mypy + pytest + llm_eval + contracts + schema + env-template-security + env.local.example profile)
```

(Black kann je nach Umgebung kurze Zusatzzeilen auf stderr schreiben; Exit-Code bleibt 0.)

## Offene Punkte

- Keine.
