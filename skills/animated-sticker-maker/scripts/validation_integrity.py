#!/usr/bin/env python3
"""Validate report evidence, state transitions, and upstream dependencies."""

from __future__ import annotations

import json
from pathlib import Path

from artifact_integrity import (
    package_fingerprint,
    render_track_fingerprint,
    report_artifact_fingerprint,
    safe_relative_file,
    sha256_path,
)


NOTE_FIELDS = ("identity", "meaning", "loop", "alpha", "small_size")


def validation_status(report: dict[str, object]) -> dict[str, object]:
    technical = report.get("technical_validation")
    visual = report.get("visual_validation")
    return {
        "aggregate": report.get("status") if isinstance(report.get("status"), str) else None,
        "technical": technical.get("status") if isinstance(technical, dict) else None,
        "visual": visual.get("status") if isinstance(visual, dict) else None,
        "deliverable_ready": report.get("deliverable_ready") is True,
    }


def _validated_technical_status(report: dict[str, object]) -> str:
    technical = report.get("technical_validation")
    if not isinstance(technical, dict):
        raise ValueError("report.technical_validation must be an object")
    status = technical.get("status")
    if status not in {"pass", "fail"}:
        raise ValueError("technical_validation.status must be 'pass' or 'fail'")
    checks = technical.get("checks")
    if not isinstance(checks, dict) or not checks:
        raise ValueError("technical_validation.checks must be a non-empty object")
    if any(not isinstance(value, bool) for value in checks.values()):
        raise ValueError("every technical_validation check must be boolean")
    expected = "pass" if all(checks.values()) else "fail"
    if status != expected:
        raise ValueError(
            f"technical_validation.status must be {expected!r} for its recorded checks"
        )
    return status


def _validated_visual_status(report: dict[str, object]) -> str:
    visual = report.get("visual_validation")
    if not isinstance(visual, dict):
        raise ValueError("report.visual_validation must be an object")
    status = visual.get("status")
    if status not in {"pending", "pass", "fail"}:
        raise ValueError("visual_validation.status must be pending, pass, or fail")
    if status in {"pass", "fail"}:
        notes = visual.get("notes")
        if not isinstance(notes, dict):
            raise ValueError("completed visual validation must contain notes")
        missing = [
            field
            for field in NOTE_FIELDS
            if not isinstance(notes.get(field), str) or not str(notes[field]).strip()
        ]
        if missing:
            raise ValueError(
                "completed visual validation notes must be non-empty: "
                + ", ".join(missing)
            )
    return status


def validate_report_state(
    report: dict[str, object], *, require_complete: bool = False
) -> dict[str, object]:
    technical = _validated_technical_status(report)
    visual = _validated_visual_status(report)
    source_complete = report.get("source_validation_complete")
    if source_complete is not None and not isinstance(source_complete, bool):
        raise ValueError("source_validation_complete must be boolean when present")
    if visual == "pass" and source_complete is False:
        raise ValueError("an export from an unvalidated source cannot pass")
    if visual == "pass" and technical != "pass":
        raise ValueError("visual validation cannot pass failed technical validation")

    if technical == "fail":
        expected_status = "technical_validation_failed"
    elif visual == "fail":
        expected_status = "visual_validation_failed"
    elif source_complete is False:
        expected_status = "diagnostic_unvalidated"
    elif visual == "pass":
        expected_status = "pass"
    else:
        expected_status = "pending_visual_validation"
    if report.get("status") != expected_status:
        raise ValueError(f"report.status must be {expected_status!r} for its validation state")
    expected_ready = expected_status == "pass"
    if report.get("deliverable_ready") is not expected_ready:
        raise ValueError(
            f"report.deliverable_ready must be {expected_ready} for status {expected_status!r}"
        )
    if require_complete and not expected_ready:
        status = validation_status(report)
        raise ValueError(f"validation is incomplete ({status})")
    return validation_status(report)


def _load_json_object(path: Path, label: str) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def validate_report_binding(report_path: Path, report: dict[str, object]) -> None:
    expected = report.get("artifact_fingerprint")
    if not isinstance(expected, str):
        raise ValueError("report has no artifact fingerprint")
    if report_artifact_fingerprint(report_path, report) != expected:
        raise ValueError("validation artifacts changed; regenerate the report")

    if report.get("artifact_scope") != "export_files":
        return
    artifacts = report.get("validation_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("export report must list validation_artifacts")
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            raise ValueError(f"validation_artifacts[{index}] must be an object")
        artifact_path = safe_relative_file(
            report_path.parent,
            artifact.get("path"),
            f"validation_artifacts[{index}].path",
        )
        if artifact.get("sha256") != sha256_path(artifact_path):
            raise ValueError(
                f"validation_artifacts[{index}].sha256 does not match its file"
            )
    package = report_path.parent.parent.parent.resolve()
    source_package_value = report.get("source_package")
    if not isinstance(source_package_value, str) or not source_package_value:
        raise ValueError("export report must declare its source_package")
    if (report_path.parent / source_package_value).resolve() != package:
        raise ValueError("export report source_package is inconsistent with its location")
    source_record = report.get("source_validation_report")
    if not isinstance(source_record, dict):
        raise ValueError("export report must bind its source validation report")
    source_report_path = package / "validation" / "report.json"
    source_report_value = source_record.get("path")
    if not isinstance(source_report_value, str) or not source_report_value:
        raise ValueError("source_validation_report.path must be non-empty")
    if (report_path.parent / source_report_value).resolve() != source_report_path:
        raise ValueError("source validation report path is inconsistent")
    if not source_report_path.is_file():
        raise FileNotFoundError(f"source validation report not found: {source_report_path}")
    if source_record.get("sha256") != sha256_path(source_report_path):
        raise ValueError("source validation report changed after export")
    source_report = _load_json_object(source_report_path, "source validation report")
    source_complete_value = report.get("source_validation_complete")
    if not isinstance(source_complete_value, bool):
        raise ValueError("export report source_validation_complete must be boolean")
    source_complete = source_complete_value
    current_source_status = validate_report_state(
        source_report,
        require_complete=source_complete,
    )
    if report.get("source_validation") != current_source_status:
        raise ValueError("export report source validation snapshot is inconsistent")
    current_source_fingerprint = package_fingerprint(package)
    if source_report.get("artifact_fingerprint") != current_source_fingerprint:
        raise ValueError("source package changed after export")
    if source_record.get("artifact_fingerprint") != current_source_fingerprint:
        raise ValueError("export report source fingerprint is inconsistent")

    frame_track = report.get("frame_track")
    if frame_track not in {"keyframes", "render"}:
        raise ValueError("export report frame_track must be 'keyframes' or 'render'")
    if frame_track == "keyframes":
        if report.get("track_validation") is not None or report.get("track_report") is not None:
            raise ValueError(
                "keyframe export report must not declare render-track validation"
            )
        if source_complete != (current_source_status["deliverable_ready"] is True):
            raise ValueError("source_validation_complete is inconsistent")
        return
    track_record = report.get("track_report")
    if not isinstance(track_record, dict):
        if source_complete is False:
            return
        raise ValueError("render export must bind its render-track report")
    track_value = track_record.get("path")
    if not isinstance(track_value, str) or not track_value:
        raise ValueError("track_report.path must be a package-relative path")
    track_relative = Path(track_value)
    if track_relative.is_absolute() or ".." in track_relative.parts:
        raise ValueError("track_report.path must stay beneath the package")
    track_path = package / track_relative
    if not track_path.is_file() or not track_path.resolve().is_relative_to(package):
        raise ValueError("render-track report is missing or escapes the package")
    if track_record.get("sha256") != sha256_path(track_path):
        raise ValueError("render-track report changed after export")
    track_report = _load_json_object(track_path, "render-track report")
    current_track_status = validate_report_state(
        track_report,
        require_complete=source_complete,
    )
    if report.get("track_validation") != current_track_status:
        raise ValueError("export report render validation snapshot is inconsistent")
    current_track_fingerprint = render_track_fingerprint(package)
    if track_report.get("artifact_fingerprint") != current_track_fingerprint:
        raise ValueError("render track changed after export")
    expected_complete = bool(
        current_source_status["deliverable_ready"] is True
        and current_track_status["deliverable_ready"] is True
    )
    if source_complete != expected_complete:
        raise ValueError("source_validation_complete is inconsistent")
