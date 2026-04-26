from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUSBAR = ROOT / "apps" / "dashboard" / "src" / "components" / "layout" / "MainConsoleStatusBar.tsx"


def test_main_console_status_bar_shows_operator_safety_labels() -> None:
    text = STATUSBAR.read_text(encoding="utf-8")
    required_fragments = [
        "Betriebsmodus",
        "Sicherheit",
        "Bitget",
        "Datenqualität",
        "Broker/Reconcile",
        "Live blockiert",
    ]
    for fragment in required_fragments:
        assert fragment in text
