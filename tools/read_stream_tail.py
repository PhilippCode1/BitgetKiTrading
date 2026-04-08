from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _ensure_shared_python_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    shared_src = repo_root / "shared" / "python" / "src"
    shared_src_str = str(shared_src)
    if shared_src.is_dir() and shared_src_str not in sys.path:
        sys.path.insert(0, shared_src_str)


def _load_env_file() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    for env_name in (
        ".env.local",
        ".env.shadow",
        ".env.production",
        ".env.test",
        ".env.local.example",
        ".env.shadow.example",
        ".env.production.example",
        ".env.test.example",
    ):
        env_path = repo_root / env_name
        if not env_path.is_file():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
        return


def main() -> int:
    _ensure_shared_python_path()
    _load_env_file()

    from shared_py.eventbus import EVENT_STREAMS, RedisStreamBus

    parser = argparse.ArgumentParser(description="Lese die letzten Redis Stream Events.")
    parser.add_argument("stream", choices=EVENT_STREAMS)
    parser.add_argument(
        "--count",
        type=int,
        default=int(os.environ.get("EVENTBUS_DEFAULT_COUNT", "10")),
    )
    args = parser.parse_args()

    bus = RedisStreamBus.from_env()
    items = bus.redis.xrevrange(args.stream, max="+", min="-", count=args.count)
    output = [
        {
            "id": message_id,
            "data": json.loads(fields.get("data", "{}")),
        }
        for message_id, fields in items
    ]
    print(json.dumps({"stream": args.stream, "count": len(output), "items": output}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
