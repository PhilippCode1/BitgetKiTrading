"""Mindest-Contract: No-Go-Doku existiert, ist nicht leer, enthaelt Harte-Blocker-Abschnitt."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NO_GO = REPO / "docs" / "production_10_10" / "no_go_rules.md"

# Letzte fortlaufend nummerierte Regel in "## Harte Blocker" (bei Erweiterung anpassen).
_EXPECTED_RULE_COUNT = 53


def _numbered_rules_in_harte_blocker(text: str) -> list[int]:
    """Extrahiert Nummern aus Zeilen wie ``53. Kein Echtgeld...`` nur bis zur naechsten Sektion."""
    if "## Harte Blocker" not in text:
        return []
    after = text.split("## Harte Blocker", 1)[1]
    for marker in ("\n## ",):
        if marker in after:
            after = after.split(marker, 1)[0]
    nums: list[int] = []
    for line in after.splitlines():
        m = re.match(r"^\s*(\d+)\.\s+", line)
        if m:
            nums.append(int(m.group(1)))
    return nums


def test_no_go_rules_file_exists_and_substantive() -> None:
    assert NO_GO.is_file(), f"fehlt: {NO_GO}"
    text = NO_GO.read_text(encoding="utf-8")
    assert len(text.strip()) > 200
    assert "# No-Go Rules" in text or "No-Go" in text
    assert "## Harte Blocker" in text or "Harte Blocker" in text
    assert "Echtgeld" in text or "Echtgeld-Live" in text


def test_no_go_rules_harte_blocker_numbering_contiguous() -> None:
    text = NO_GO.read_text(encoding="utf-8")
    nums = _numbered_rules_in_harte_blocker(text)
    expected = list(range(1, _EXPECTED_RULE_COUNT + 1))
    assert nums == expected, (
        f"Erwartet fortlaufend 1..{_EXPECTED_RULE_COUNT}, erhalten: "
        f"{nums[:5]}... (len={len(nums)})"
    )


def test_no_go_rules_owner_release_machine_gate_documented() -> None:
    """Regel 53 / Owner-Datei: maschinenlesbar, gitignored, nicht committen."""
    text = NO_GO.read_text(encoding="utf-8")
    lower = text.lower()
    assert "owner_private_live_release.json" in text
    assert "gitignored" in lower or "git-index" in lower or "nicht ins repository" in lower
