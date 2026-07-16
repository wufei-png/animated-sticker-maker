#!/usr/bin/env python3
"""Deterministic checks for one animated-sticker artifact boundary."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, TypeVar

from PIL import Image

from artifact_integrity import safe_relative_file, sha256_path
from export_platform_gif import gif_safe_durations
from media_validation import alpha_metrics, validate_gif, validate_sticker_webp
from motion_schema import validate_motion, validate_render_pixel_budget
from validation_integrity import validate_report_binding, validate_report_state


JSON_SCHEMA_VERSION = 1
EXIT_CODES = {"healthy": 0, "invalid": 1, "incomplete": 2}
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


def motion_variant(motion: dict[str, object]) -> bool:
    """Return whether a motion plan is packaged; reject ambiguous variants."""
    has_working_reference = "reference_image" in motion
    has_packaged_reference = "reference" in motion
    if has_working_reference == has_packaged_reference:
        raise ValueError(
            "motion must contain exactly one of reference_image or reference"
        )
    return has_packaged_reference


def diagnose_motion(path: Path, kind: str = "motion") -> Diagnosis:
    diagnosis = Diagnosis(kind, path)
    motion = diagnosis.capture(
        "motion.json",
        lambda: load_json_object(path),
        "motion plan is readable JSON",
        path,
    )
    if motion is None:
        return diagnosis
    packaged = diagnosis.capture(
        "motion.variant",
        lambda: motion_variant(motion),
        "motion plan has one unambiguous variant",
        path,
    )
    if packaged is None:
        return diagnosis
    diagnosis.capture(
        "motion.schema",
        lambda: validate_motion(motion, packaged=packaged),
        f"motion schema v2 is valid ({'packaged' if packaged else 'working'})",
        path,
    )
    return diagnosis


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
