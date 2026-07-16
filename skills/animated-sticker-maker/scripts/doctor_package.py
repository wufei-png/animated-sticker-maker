#!/usr/bin/env python3
"""Doctor checks for package source and optional render-track artifacts."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from artifact_integrity import safe_relative_file, sha256_path
from doctor_core import Diagnosis, diagnose_report_core, load_json_object
from media_validation import alpha_metrics, validate_sticker_webp
from motion_schema import validate_motion, validate_render_pixel_budget


def inspect_frame_set(
    diagnosis: Diagnosis,
    prefix: str,
    source_root: Path,
    entries: list[dict[str, object]],
    expected_size: tuple[int, int],
    *,
    require_unique: bool,
    enforce_pixel_budget: bool = False,
) -> list[dict[str, object]]:
    metrics: list[dict[str, object]] = []
    aggregate_pixels = 0
    for index, entry in enumerate(entries):
        path = diagnosis.capture(
            f"{prefix}.{index}.path",
            lambda entry=entry, index=index: safe_relative_file(
                source_root,
                entry.get("file"),
                f"{prefix}[{index}].file",
            ),
            "frame path is present and contained",
            source_root,
        )
        if path is None:
            continue
        try:
            with Image.open(path) as source:
                source.load()
                image_format = source.format
                source_mode = source.mode
                source_size = source.size
                aggregate_pixels += source.width * source.height
                rgba = source.convert("RGBA")
        except Exception as exc:
            diagnosis.add(
                f"{prefix}.{index}.readable",
                "error",
                str(exc),
                path,
            )
            continue
        diagnosis.add(
            f"{prefix}.{index}.readable",
            "pass",
            "frame is readable",
            path,
        )
        diagnosis.boolean(
            f"{prefix}.{index}.format",
            image_format == "PNG",
            "packaged frame is PNG",
            f"packaged frame format is {image_format!r}, expected PNG",
            path,
        )
        diagnosis.boolean(
            f"{prefix}.{index}.mode",
            source_mode == "RGBA",
            "packaged frame is RGBA",
            f"packaged frame mode is {source_mode!r}, expected RGBA",
            path,
        )
        diagnosis.boolean(
            f"{prefix}.{index}.size",
            source_size == expected_size,
            "frame matches the motion canvas",
            f"frame size {source_size} does not match {expected_size}",
            path,
        )
        frame_metrics = alpha_metrics(rgba)
        diagnosis.boolean(
            f"{prefix}.{index}.alpha-border",
            frame_metrics["border_is_transparent"] is True,
            "frame border is transparent",
            "frame border is not fully transparent",
            path,
        )
        diagnosis.boolean(
            f"{prefix}.{index}.visible",
            frame_metrics["alpha_bbox"] is not None,
            "frame contains visible pixels",
            "frame contains no visible pixels",
            path,
        )
        metrics.append(frame_metrics)
    if require_unique and len(metrics) == len(entries):
        diagnosis.boolean(
            f"{prefix}.unique",
            len({metric["pixel_sha256"] for metric in metrics}) == len(metrics),
            "all authored frames are unique",
            "authored frames contain duplicate pixel content",
            source_root,
        )
    if enforce_pixel_budget and metrics:
        diagnosis.capture(
            f"{prefix}.input-pixels",
            lambda: validate_render_pixel_budget(aggregate_pixels),
            "render frames stay within the aggregate input-pixel limit",
            source_root,
        )
    return metrics


def diagnose_reference(
    diagnosis: Diagnosis,
    package: Path,
    motion: dict[str, object],
    report: dict[str, object] | None,
) -> None:
    reference_path = package / "source" / "reference.json"
    reference = diagnosis.capture(
        "package.reference.json",
        lambda: load_json_object(reference_path),
        "reference metadata is readable JSON",
        reference_path,
    )
    if reference is None:
        return
    motion_reference = motion.get("reference")
    diagnosis.boolean(
        "package.reference.motion",
        isinstance(motion_reference, dict)
        and all(
            reference.get(field) == motion_reference.get(field)
            for field in ("filename", "sha256", "included_path")
        ),
        "motion reference agrees with reference metadata",
        "motion reference and source/reference.json disagree",
        reference_path,
    )
    if report is not None:
        diagnosis.boolean(
            "package.reference.report",
            report.get("reference") == reference,
            "package report records the exact reference metadata",
            "package report reference metadata is inconsistent",
            reference_path,
        )
    included_path = reference.get("included_path")
    if included_path is not None:
        included = diagnosis.capture(
            "package.reference.included-path",
            lambda: safe_relative_file(
                package / "source",
                included_path,
                "reference.included_path",
            ),
            "included reference path is present and contained",
            package / "source",
        )
        if included is not None:
            diagnosis.boolean(
                "package.reference.included-sha256",
                reference.get("sha256") == sha256_path(included),
                "included reference matches its declared SHA-256",
                "included reference does not match its declared SHA-256",
                included,
            )


def diagnose_primary_package(
    diagnosis: Diagnosis,
    package: Path,
    motion: dict[str, object],
    report: dict[str, object] | None,
) -> None:
    source = package / "source"
    entries = motion["frames"]
    assert isinstance(entries, list)
    canvas = tuple(int(value) for value in motion["canvas"])
    metrics = inspect_frame_set(
        diagnosis,
        "package.frames",
        source,
        entries,
        canvas,
        require_unique=True,
    )
    semantic_hold = motion.get("semantic_hold_frame")
    if semantic_hold is not None:
        matches = sum(
            1 for entry in entries if entry.get("file") == semantic_hold
        )
        diagnosis.boolean(
            "package.semantic-hold",
            matches == 1,
            "semantic hold names exactly one authored frame",
            "semantic hold must name exactly one authored frame",
            source / str(semantic_hold),
        )

    durations = [int(entry["duration_ms"]) for entry in entries]
    sticker = package / "sticker.webp"
    webp_checks = diagnosis.capture(
        "package.webp.readable",
        lambda: validate_sticker_webp(
            sticker,
            canvas,
            len(entries),
            0 if motion["loop"] is True else 1,
            durations,
        ),
        "sticker.webp is readable and structurally valid",
        sticker,
    )
    if webp_checks is not None:
        for name, passed in webp_checks.items():
            diagnosis.boolean(
                f"package.webp.{name}",
                passed,
                f"{name} passed",
                f"{name} failed",
                sticker,
            )
    if report is not None:
        expected_metadata = {
            "canvas": list(canvas),
            "frame_count": len(entries),
            "total_duration_ms": sum(durations),
            "resampling": motion["resampling"],
        }
        diagnosis.boolean(
            "package.report.metadata",
            all(report.get(field) == value for field, value in expected_metadata.items()),
            "package report metadata matches the motion plan",
            "package report metadata does not match the motion plan",
            package / "validation" / "report.json",
        )
        if len(metrics) == len(entries):
            diagnosis.boolean(
                "package.report.frame-evidence",
                report.get("frames") == metrics,
                "package report frame evidence matches current frames",
                "package report frame evidence does not match current frames",
                package / "validation" / "report.json",
            )
    diagnose_reference(diagnosis, package, motion, report)


def diagnose_render_track(
    diagnosis: Diagnosis,
    package: Path,
    motion: dict[str, object],
    report: dict[str, object] | None,
) -> None:
    render = motion.get("render")
    if not isinstance(render, dict):
        diagnosis.add(
            "render.declared",
            "error",
            "motion plan does not declare a render track",
            package / "source" / "motion.json",
        )
        return
    entries = render["frames"]
    assert isinstance(entries, list)
    canvas = tuple(int(value) for value in motion["canvas"])
    metrics = inspect_frame_set(
        diagnosis,
        "render.frames",
        package / "source",
        entries,
        canvas,
        require_unique=False,
        enforce_pixel_budget=True,
    )
    durations = [int(entry["duration_ms"]) for entry in entries]
    if report is not None:
        expected_metadata = {
            "target_fps": render["target_fps"],
            "frame_count": len(entries),
            "total_duration_ms": sum(durations),
        }
        diagnosis.boolean(
            "render.report.metadata",
            all(report.get(field) == value for field, value in expected_metadata.items()),
            "render report metadata matches the motion plan",
            "render report metadata does not match the motion plan",
            package / "validation" / "render-report.json",
        )
        if len(metrics) == len(entries):
            diagnosis.boolean(
                "render.report.frame-evidence",
                report.get("frames") == metrics,
                "render report frame evidence matches current frames",
                "render report frame evidence does not match current frames",
                package / "validation" / "render-report.json",
            )


def diagnose_package(path: Path) -> Diagnosis:
    package = path.resolve()
    diagnosis = Diagnosis("package", package)
    motion_path = package / "source" / "motion.json"
    report_path = package / "validation" / "report.json"
    for check_id, required in (
        ("package.structure.motion", motion_path),
        ("package.structure.frames", package / "source" / "frames"),
        ("package.structure.report", report_path),
        ("package.structure.webp", package / "sticker.webp"),
    ):
        diagnosis.boolean(
            check_id,
            required.is_dir() if required.name == "frames" else required.is_file(),
            f"required package path exists: {required.name}",
            f"required package path is missing: {required}",
            required,
        )
    motion = diagnosis.capture(
        "package.motion",
        lambda: validate_motion(load_json_object(motion_path), packaged=True),
        "packaged motion schema v2 is valid",
        motion_path,
    )
    report = diagnose_report_core(
        diagnosis,
        report_path,
        "package.report",
        expected_scope="package_source",
    )
    if motion is None:
        return diagnosis
    diagnose_primary_package(diagnosis, package, motion, report)
    render = motion.get("render")
    render_report_path = package / "validation" / "render-report.json"
    if isinstance(render, dict):
        render_report = diagnose_report_core(
            diagnosis,
            render_report_path,
            "render.report",
            expected_scope="render_track",
        )
        diagnose_render_track(diagnosis, package, motion, render_report)
        if report is not None:
            expected_summary = {
                "target_fps": render["target_fps"],
                "frame_count": len(render["frames"]),
                "total_duration_ms": sum(
                    int(entry["duration_ms"]) for entry in render["frames"]
                ),
            }
            diagnosis.boolean(
                "package.report.render-summary",
                report.get("render_track") == expected_summary,
                "package report render summary matches the declared track",
                "package report render summary is inconsistent",
                report_path,
            )
    else:
        diagnosis.boolean(
            "package.render-report.absent",
            not render_report_path.exists(),
            "package has no undeclared render report",
            "package contains a render report without a declared render track",
            render_report_path,
        )
    return diagnosis
