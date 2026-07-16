#!/usr/bin/env python3
"""Doctor checks for validation reports and platform export media."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from artifact_integrity import safe_relative_file, sha256_path
from doctor_core import Diagnosis, diagnose_report_core, load_json_object
from doctor_package import diagnose_primary_package, diagnose_render_track
from gif_export_core import gif_safe_durations
from media_validation import alpha_metrics, validate_gif
from motion_schema import validate_motion


def add_dependency_diagnosis(
    diagnosis: Diagnosis,
    prefix: str,
    report_path: Path,
) -> None:
    dependency = diagnose_report(report_path)
    for check in dependency.checks:
        diagnosis.add(
            f"{prefix}.{check.id}",
            check.status,
            check.message,
            Path(check.path) if check.path is not None else None,
        )


def diagnose_export_media(
    diagnosis: Diagnosis,
    report_path: Path,
    report: dict[str, object],
) -> None:
    package = report_path.parent.parent.parent.resolve()
    motion_path = package / "source" / "motion.json"
    motion = diagnosis.capture(
        "export.source.motion",
        lambda: validate_motion(load_json_object(motion_path), packaged=True),
        "export source motion schema v2 is valid",
        motion_path,
    )
    if motion is None:
        return
    source_report_path = package / "validation" / "report.json"
    add_dependency_diagnosis(
        diagnosis,
        "export.source-report",
        source_report_path,
    )
    frame_track = report.get("frame_track")
    if frame_track == "render":
        render = motion.get("render")
        if not isinstance(render, dict):
            diagnosis.add(
                "export.track",
                "error",
                "render export has no declared render track",
                motion_path,
            )
            return
        entries = render["frames"]
        track_report = report.get("track_report")
        if isinstance(track_report, dict) and isinstance(track_report.get("path"), str):
            track_path = diagnosis.capture(
                "export.track-report.path",
                lambda: safe_relative_file(
                    package,
                    track_report.get("path"),
                    "track_report.path",
                ),
                "render-track report path is present and contained",
                package,
            )
            if track_path is not None:
                add_dependency_diagnosis(
                    diagnosis,
                    "export.track-report",
                    track_path,
                )
    elif frame_track == "keyframes":
        entries = motion["frames"]
    else:
        return
    assert isinstance(entries, list)
    source_durations = [int(entry["duration_ms"]) for entry in entries]
    total_duration = sum(source_durations)
    gif = report.get("gif")
    if not isinstance(gif, dict):
        diagnosis.add(
            "export.gif.record",
            "error",
            "export report must contain a gif object",
            report_path,
        )
        return
    gif_path = diagnosis.capture(
        "export.gif.path",
        lambda: safe_relative_file(
            report_path.parent,
            gif.get("path"),
            "gif.path",
        ),
        "GIF path is present and contained",
        report_path.parent,
    )
    selected_fps = gif.get("selected_fps")
    if selected_fps is None:
        expected_count = len(entries)
        expected_durations = source_durations
        allow_frame_collapse = False
    elif (
        isinstance(selected_fps, int)
        and not isinstance(selected_fps, bool)
        and 1 <= selected_fps <= 100
    ):
        expected_count = max(2, round(total_duration * selected_fps / 1000))
        expected_durations = gif_safe_durations(total_duration, expected_count)
        allow_frame_collapse = True
    else:
        diagnosis.add(
            "export.gif.selected-fps",
            "error",
            "gif.selected_fps must be null or an integer from 1 to 100",
            report_path,
        )
        return
    expected_report_metadata = {
        "source_frame_count": len(entries),
        "source_total_duration_ms": total_duration,
        "frame_count": expected_count,
        "total_duration_ms": sum(expected_durations),
    }
    diagnosis.boolean(
        "export.report.timeline",
        all(
            report.get(field) == value
            for field, value in expected_report_metadata.items()
        ),
        "export report timeline matches its source track",
        "export report timeline does not match its source track",
        report_path,
    )
    canvas = report.get("canvas")
    if not (
        isinstance(canvas, list)
        and len(canvas) == 2
        and all(
            isinstance(value, int)
            and not isinstance(value, bool)
            and value > 0
            for value in canvas
        )
    ):
        diagnosis.add(
            "export.canvas",
            "error",
            "export report canvas must contain two positive integers",
            report_path,
        )
        return
    if gif_path is not None:
        actual_validation = diagnosis.capture(
            "export.gif.media",
            lambda: validate_gif(
                gif_path,
                (int(canvas[0]), int(canvas[1])),
                expected_count,
                expected_durations,
                bool(motion["loop"]),
                allow_frame_collapse=allow_frame_collapse,
            ),
            "GIF media matches the declared source timeline",
            gif_path,
        )
        diagnosis.boolean(
            "export.gif.bytes",
            gif.get("bytes") == gif_path.stat().st_size,
            "GIF byte count matches the file",
            "GIF byte count does not match the file",
            gif_path,
        )
        diagnosis.boolean(
            "export.gif.sha256",
            gif.get("sha256") == sha256_path(gif_path),
            "GIF SHA-256 matches the file",
            "GIF SHA-256 does not match the file",
            gif_path,
        )
        if actual_validation is not None:
            diagnosis.boolean(
                "export.gif.validation-evidence",
                gif.get("validation") == actual_validation,
                "GIF validation evidence matches current media",
                "GIF validation evidence does not match current media",
                report_path,
            )
    preview = report.get("preview")
    if preview is not None:
        if not isinstance(preview, dict):
            diagnosis.add(
                "export.preview.record",
                "error",
                "preview must be null or an object",
                report_path,
            )
            return
        preview_path = diagnosis.capture(
            "export.preview.path",
            lambda: safe_relative_file(
                report_path.parent,
                preview.get("path"),
                "preview.path",
            ),
            "preview path is present and contained",
            report_path.parent,
        )
        if preview_path is not None:
            try:
                with Image.open(preview_path) as image:
                    image.load()
                    preview_format = image.format
                    preview_size = image.size
                    preview_metrics = alpha_metrics(image.convert("RGBA"))
            except Exception as exc:
                diagnosis.add(
                    "export.preview.media",
                    "error",
                    str(exc),
                    preview_path,
                )
            else:
                diagnosis.boolean(
                    "export.preview.format",
                    preview_format == "PNG",
                    "preview is PNG",
                    f"preview format is {preview_format!r}, expected PNG",
                    preview_path,
                )
                diagnosis.boolean(
                    "export.preview.size",
                    preview_size == (int(canvas[0]), int(canvas[1])),
                    "preview matches the export canvas",
                    "preview does not match the export canvas",
                    preview_path,
                )
                diagnosis.boolean(
                    "export.preview.visible",
                    preview_metrics["alpha_bbox"] is not None,
                    "preview contains visible pixels",
                    "preview contains no visible pixels",
                    preview_path,
                )
                diagnosis.boolean(
                    "export.preview.alpha-border",
                    preview_metrics["border_is_transparent"] is True,
                    "preview border is transparent",
                    "preview border is not fully transparent",
                    preview_path,
                )
            diagnosis.boolean(
                "export.preview.bytes",
                preview.get("bytes") == preview_path.stat().st_size,
                "preview byte count matches the file",
                "preview byte count does not match the file",
                preview_path,
            )
            diagnosis.boolean(
                "export.preview.sha256",
                preview.get("sha256") == sha256_path(preview_path),
                "preview SHA-256 matches the file",
                "preview SHA-256 does not match the file",
                preview_path,
            )


def diagnose_report(path: Path, kind: str = "report") -> Diagnosis:
    report_path = path.resolve()
    diagnosis = Diagnosis(kind, report_path)
    report = diagnose_report_core(diagnosis, report_path, "report")
    if report is None:
        return diagnosis
    scope = report.get("artifact_scope")
    if scope == "package_source":
        package = report_path.parent.parent
        motion_path = package / "source" / "motion.json"
        motion = diagnosis.capture(
            "report.package.motion",
            lambda: validate_motion(load_json_object(motion_path), packaged=True),
            "package motion schema v2 is valid",
            motion_path,
        )
        if motion is not None:
            diagnose_primary_package(diagnosis, package, motion, report)
    elif scope == "render_track":
        package = report_path.parent.parent
        motion_path = package / "source" / "motion.json"
        motion = diagnosis.capture(
            "report.render.motion",
            lambda: validate_motion(load_json_object(motion_path), packaged=True),
            "package motion schema v2 is valid",
            motion_path,
        )
        if motion is not None:
            diagnose_render_track(diagnosis, package, motion, report)
    elif scope == "export_files":
        diagnose_export_media(diagnosis, report_path, report)
    else:
        diagnosis.add(
            "report.scope",
            "error",
            "unsupported report artifact_scope",
            report_path,
        )
    return diagnosis


def diagnose_export(path: Path) -> Diagnosis:
    diagnosis = diagnose_report(path, kind="export")
    report = None
    try:
        report = load_json_object(path)
    except Exception:
        pass
    if report is not None:
        diagnosis.boolean(
            "export.scope",
            report.get("artifact_scope") == "export_files",
            "report describes an export artifact",
            "export target must use artifact_scope 'export_files'",
            path,
        )
    return diagnosis
