from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
ALERT_ENGINE_SRC = ROOT / "services" / "alert-engine" / "src"
for candidate in (ROOT / "shared" / "python" / "src", ALERT_ENGINE_SRC, ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from alert_engine.telegram.commands import ALLOWED_TELEGRAM_COMMANDS, READONLY_TELEGRAM_COMMANDS
from shared_py.telegram_chat_contract import FORBIDDEN_CHAT_STRATEGY_MUTATION_VERBS


def test_allowlist_excludes_arbitrary_commands() -> None:
    assert "/set_weight" not in ALLOWED_TELEGRAM_COMMANDS
    assert "/risk_limit" not in ALLOWED_TELEGRAM_COMMANDS
    assert "/playbook" not in ALLOWED_TELEGRAM_COMMANDS
    assert "/release_step1" in ALLOWED_TELEGRAM_COMMANDS
    assert "/help" in READONLY_TELEGRAM_COMMANDS


def test_forbidden_verbs_not_in_allowlist() -> None:
    for verb in sorted(FORBIDDEN_CHAT_STRATEGY_MUTATION_VERBS):
        assert f"/{verb}" not in ALLOWED_TELEGRAM_COMMANDS
