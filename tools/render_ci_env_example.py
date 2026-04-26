#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--placeholder", default="ci_repeatable_secret_min_32_chars_x")
    args = parser.parse_args()

    src = args.input.read_text(encoding="utf-8")
    rendered = src.replace("<SET_ME>", args.placeholder)
    args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
