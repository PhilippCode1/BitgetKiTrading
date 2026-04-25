# Evidence-Registry (Prompt-Ergaenzungen)

Diese Datei dient dazu, kuenftige Arbeits-Prompts **eindeutig** abzulegen, welche Artefakte wohin gelifert wurden. Das Audit-Tool liest **optional** `docs/release_evidence/`-Dateien mit definierten Markern; reine Doku in dieser Tabelle ersetzt **kein** L4/L5, erhoeht aber die Rückverfolgbarkeit.

| Prompt / Ticket | Kategorie-IDs | Neuer/aktualisierter Pfad (Repo) | Evidence-Ziel (L0–L5) | Maschinenmarker (eine Zeile) |
| ----------------- | --------------- | --------------------------------- | ---------------------- | ----------------------------- |
| 01 (Baseline)   | (alle)         | `docs/production_10_10/*`         | L0–L3-Definitionen     | (Startschicht)                |
| 02 (Branch-Protect) | ci/merge, org | `tools/check_github_branch_protection.py`, `docs/ci_release_gates.md` | L3 pruefbar; L4 API-JSON/Report | kein PASS ohne Token/200-API |

Hinweis: **Einträge ohne Dateinachweis in `docs/release_evidence/…`** (oder ohne CI-traceable Artefakt) bleiben in der Wahrheits-Map bei **Doku-Claim (L0)** bzw. dem vom Tool erkannten Max-Level.
