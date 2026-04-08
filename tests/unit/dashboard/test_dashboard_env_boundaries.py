from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_SRC = REPO_ROOT / "apps" / "dashboard" / "src"
PROCESS_ENV_PATTERN = re.compile(r"process\.env\.([A-Z0-9_]+)")

ALLOWED_ENV_FILES: dict[str, set[str] | str] = {
    "lib/env.ts": "NEXT_PUBLIC_OR_NODE_ENV",
    "lib/runtime-env-gate.ts": {
        "API_GATEWAY_URL",
        "DASHBOARD_ENFORCE_ENV",
        "DASHBOARD_GATEWAY_AUTHORIZATION",
        "NEXT_PUBLIC_API_BASE_URL",
        "NEXT_PUBLIC_WS_BASE_URL",
        "NODE_ENV",
    },
    "lib/server-env.ts": {
        "API_GATEWAY_URL",
        "COMMERCIAL_TELEGRAM_REQUIRED_FOR_CONSOLE",
        "DASHBOARD_GATEWAY_AUTHORIZATION",
        "LOG_FORMAT",
        "LOG_LEVEL",
        "NEXT_PUBLIC_API_BASE_URL",
        "NODE_ENV",
        "PAYMENT_MOCK_WEBHOOK_SECRET",
    },
}


def test_dashboard_process_env_usage_is_restricted_to_env_modules() -> None:
    unexpected: list[str] = []

    for path in DASHBOARD_SRC.rglob("*.ts"):
        rel = path.relative_to(DASHBOARD_SRC).as_posix()
        env_names = PROCESS_ENV_PATTERN.findall(path.read_text(encoding="utf-8"))
        if not env_names:
            continue

        allowed = ALLOWED_ENV_FILES.get(rel)
        if allowed is None:
            unexpected.append(f"{rel}: {', '.join(sorted(env_names))}")
            continue

        if allowed == "NEXT_PUBLIC_ONLY":
            invalid = [name for name in env_names if not name.startswith("NEXT_PUBLIC_")]
        elif allowed == "NEXT_PUBLIC_OR_NODE_ENV":
            invalid = [
                name
                for name in env_names
                if not (name.startswith("NEXT_PUBLIC_") or name == "NODE_ENV")
            ]
        else:
            invalid = [name for name in env_names if name not in allowed]
        if invalid:
            unexpected.append(f"{rel}: {', '.join(sorted(invalid))}")

    assert unexpected == [], (
        "Dashboard darf `process.env` nur in den erlaubten Env-Modulen lesen: "
        + "; ".join(unexpected)
    )
