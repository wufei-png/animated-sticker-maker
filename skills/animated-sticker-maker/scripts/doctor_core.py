#!/usr/bin/env python3
"""Shared result model and report-state checks for Doctor."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, TypeVar

from validation_integrity import validate_report_binding, validate_report_state


JSON_SCHEMA_VERSION = 1
T = TypeVar("T")


@dataclass(frozen=True)
class Check:
    id: str
    status: str
    message: str
    path: str | None = None


class Diagnosis:
    def __init__(self, kind: str, path: Path) -> None:
        self.kind = kind
        self.path = path.resolve()
        self.checks: list[Check] = []

    def add(
        self,
        check_id: str,
        status: str,
        message: str,
        path: Path | None = None,
    ) -> None:
        self.checks.append(
            Check(
                id=check_id,
                status=status,
                message=message,
                path=str(path.resolve()) if path is not None else None,
            )
        )

    def boolean(
        self,
        check_id: str,
        condition: bool,
        success: str,
        failure: str,
        path: Path | None = None,
    ) -> bool:
        self.add(
            check_id,
            "pass" if condition else "error",
            success if condition else failure,
            path,
        )
        return condition

    def capture(
        self,
        check_id: str,
        action: Callable[[], T],
        success: str,
        path: Path | None = None,
    ) -> T | None:
        try:
            value = action()
        except Exception as exc:
            self.add(check_id, "error", str(exc), path)
            return None
        self.add(check_id, "pass", success, path)
        return value

    @property
    def status(self) -> str:
        if any(check.status == "error" for check in self.checks):
            return "invalid"
        if any(check.status == "warning" for check in self.checks):
            return "incomplete"
        return "healthy"

    def result(self) -> dict[str, object]:
        checks = [asdict(check) for check in self.checks]
        return {
            "schema_version": JSON_SCHEMA_VERSION,
            "status": self.status,
            "target": {"kind": self.kind, "path": str(self.path)},
            "checks": checks,
            "errors": [
                check for check in checks if check["status"] == "error"
            ],
            "warnings": [
                check for check in checks if check["status"] == "warning"
            ],
        }


def load_json_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def add_report_phase_checks(
    diagnosis: Diagnosis,
    prefix: str,
    report: dict[str, object],
    path: Path,
) -> None:
    technical = report.get("technical_validation")
    technical_status = (
        technical.get("status") if isinstance(technical, dict) else None
    )
    diagnosis.add(
        f"{prefix}.technical",
        "pass" if technical_status == "pass" else "error",
        (
            "technical validation passed"
            if technical_status == "pass"
            else f"technical validation is {technical_status!r}"
        ),
        path,
    )
    visual = report.get("visual_validation")
    visual_status = visual.get("status") if isinstance(visual, dict) else None
    if visual_status == "pass":
        status = "pass"
        message = "visual validation passed"
    elif visual_status == "pending":
        status = "warning"
        message = "visual validation is pending"
    else:
        status = "error"
        message = f"visual validation is {visual_status!r}"
    diagnosis.add(f"{prefix}.visual", status, message, path)


def diagnose_report_core(
    diagnosis: Diagnosis,
    report_path: Path,
    prefix: str,
    expected_scope: str | None = None,
) -> dict[str, object] | None:
    report = diagnosis.capture(
        f"{prefix}.json",
        lambda: load_json_object(report_path),
        "validation report is readable JSON",
        report_path,
    )
    if report is None:
        return None
    if expected_scope is not None:
        diagnosis.boolean(
            f"{prefix}.scope",
            report.get("artifact_scope") == expected_scope,
            f"report scope is {expected_scope}",
            f"report scope must be {expected_scope!r}",
            report_path,
        )
    state = diagnosis.capture(
        f"{prefix}.state",
        lambda: validate_report_state(report),
        "report state is internally consistent",
        report_path,
    )
    if state is not None:
        add_report_phase_checks(diagnosis, prefix, report, report_path)
    diagnosis.capture(
        f"{prefix}.binding",
        lambda: validate_report_binding(report_path, report),
        "report is bound to unchanged artifacts and upstream evidence",
        report_path,
    )
    return report
