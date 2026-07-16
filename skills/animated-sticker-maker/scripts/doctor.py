#!/usr/bin/env python3
"""Read-only diagnosis for one animated-sticker artifact boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from doctor_checks import EXIT_CODES, diagnose, print_human


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose one animated-sticker artifact boundary without modifying it."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the stable JSON schema instead of human-readable output",
    )
    subparsers = parser.add_subparsers(dest="kind")
    for kind, help_text in (
        ("motion", "diagnose one working or packaged motion plan"),
        ("package", "diagnose one complete package directory"),
        ("report", "diagnose one validation report and its bound artifact"),
        ("export", "diagnose one export report and its bound files"),
    ):
        subparser = subparsers.add_parser(kind, help=help_text)
        subparser.add_argument("path", type=Path)
    args = parser.parse_args()
    result = diagnose(args.kind, getattr(args, "path", None)).result()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print_human(result)
    raise SystemExit(EXIT_CODES[str(result["status"])])


if __name__ == "__main__":
    main()
