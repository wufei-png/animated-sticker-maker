#!/usr/bin/env python3
"""Public Doctor dispatcher for one animated-sticker artifact boundary."""

from __future__ import annotations

from pathlib import Path

from doctor_core import Diagnosis
from doctor_motion import diagnose_motion
from doctor_package import diagnose_package
from doctor_report import diagnose_export, diagnose_report


EXIT_CODES = {"healthy": 0, "invalid": 1, "incomplete": 2}


def infer_target(path: Path) -> tuple[str, Path] | None:
    root = path.resolve()
    candidates: list[tuple[str, Path]] = []
    if (
        (root / "source" / "motion.json").is_file()
        and (root / "validation" / "report.json").is_file()
    ):
        candidates.append(("package", root))
    if (root / "motion.json").is_file():
        candidates.append(("motion", root / "motion.json"))
    export_reports = sorted(root.glob("*.export-report.json"))
    candidates.extend(("export", report) for report in export_reports)
    for name in ("report.json", "render-report.json"):
        if (root / name).is_file():
            candidates.append(("report", root / name))
    if len(candidates) != 1:
        return None
    return candidates[0]


def diagnose(kind: str | None, path: Path | None) -> Diagnosis:
    if kind is None:
        root = Path.cwd()
        inferred = infer_target(root)
        if inferred is None:
            diagnosis = Diagnosis("unknown", root)
            diagnosis.add(
                "doctor.target.detect",
                "error",
                "current directory must match exactly one motion, package, report, or export boundary",
                root,
            )
            return diagnosis
        kind, path = inferred
    assert path is not None
    if kind == "motion":
        return diagnose_motion(path)
    if kind == "package":
        return diagnose_package(path)
    if kind == "report":
        return diagnose_report(path)
    if kind == "export":
        return diagnose_export(path)
    raise ValueError(f"unsupported doctor target: {kind}")


def print_human(result: dict[str, object]) -> None:
    target = result["target"]
    assert isinstance(target, dict)
    print(
        f"doctor: {result['status']} "
        f"{target['kind']} {target['path']}"
    )
    for check in result["checks"]:
        assert isinstance(check, dict)
        label = str(check["status"]).upper()
        suffix = f" ({check['path']})" if check.get("path") else ""
        print(f"{label:7} {check['id']}: {check['message']}{suffix}")
