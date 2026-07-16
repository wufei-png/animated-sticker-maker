#!/usr/bin/env python3
"""Generate one read-only HTML review page for one validation report."""

from __future__ import annotations

import argparse
from pathlib import Path

from review_page import generate_review


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a read-only local HTML review page for one exact "
            "validation report."
        )
    )
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--reference-image",
        type=Path,
        help=(
            "exact original reference image; required only when the package "
            "does not include its bound reference"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "direct child of the report directory; defaults to "
            "<report-stem>.review.html"
        ),
    )
    args = parser.parse_args()
    output = generate_review(
        args.report,
        reference_image=args.reference_image,
        output=args.output,
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
