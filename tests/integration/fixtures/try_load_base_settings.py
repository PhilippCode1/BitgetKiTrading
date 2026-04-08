"""Von Subprocess aufgerufen: laedt BaseServiceSettings aus os.environ; Exit 0 bei ValueError."""

from __future__ import annotations


def main() -> int:
    from config.settings import BaseServiceSettings

    try:
        BaseServiceSettings()
    except ValueError:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
