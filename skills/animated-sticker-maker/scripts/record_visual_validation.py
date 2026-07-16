#!/usr/bin/env python3
"""Record visual validation notes for the exact artifacts in a report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validation_integrity import (
    NOTE_FIELDS,
    validate_report_binding,
    validate_report_state,
)


def update_report(args: argparse.Namespace) -> None:
    report = json.loads(args.report.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("validation report must contain a JSON object")
    state = validate_report_state(report)
    validate_report_binding(args.report, report)

    technical_status = state["technical"]
    if args.status == "pass" and technical_status != "pass":
        raise ValueError(
            "cannot pass visual validation before technical validation passes"
        )
    if args.status == "pass" and report.get("source_validation_complete") is False:
        raise ValueError(
            "diagnostic export from an unvalidated source cannot become deliverable"
        )

    notes = {field: getattr(args, field).strip() for field in NOTE_FIELDS}
    empty_notes = [field for field, note in notes.items() if not note]
    if empty_notes:
        raise ValueError(
            "visual validation notes must be non-empty: " + ", ".join(empty_notes)
        )
    report["visual_validation"] = {"status": args.status, "notes": notes}
    if technical_status != "pass":
        report["status"] = "technical_validation_failed"
    elif args.status == "pass":
        report["status"] = "pass"
    else:
        report["status"] = "visual_validation_failed"
    report["deliverable_ready"] = report["status"] == "pass"
    validate_report_state(report)

    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Recorded visual validation: {args.status} -> {args.report}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--status", choices=("pass", "fail"), required=True)
    for field in NOTE_FIELDS:
        parser.add_argument(f"--{field.replace('_', '-')}", required=True)
    update_report(parser.parse_args())


if __name__ == "__main__":
    main()
