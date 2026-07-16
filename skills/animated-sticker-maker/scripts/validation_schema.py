#!/usr/bin/env python3
"""Closed structural contract for current Validation Report schema v1."""

from __future__ import annotations

import re


NOTE_FIELDS = ("identity", "meaning", "loop", "alpha", "small_size")
GIF_CHECK_FIELDS = {
    "gif_is_gif",
    "size_matches",
    "frame_count_matches",
    "durations_preserved",
    "loop_matches",
    "all_borders_transparent",
}
GIF_COLOR_CANDIDATES = {255, 224, 192, 160, 128, 96, 64, 48, 32}
PREVIEW_COLOR_CANDIDATES = {256, 192, 128, 96, 64, 48, 32, 24, 16}
COMMON_REPORT_FIELDS = {
    "schema_version",
    "status",
    "deliverable_ready",
    "artifact_scope",
    "policy_overrides",
    "artifact_fingerprint",
    "technical_validation",
    "visual_validation",
}
SCOPE_REPORT_FIELDS = {
    "package_source": {
        "canvas",
        "frame_count",
        "total_duration_ms",
        "resampling",
        "webp_encoding",
        "reference",
        "render_track",
        "frames",
    },
    "render_track": {
        "target_fps",
        "frame_count",
        "total_duration_ms",
        "frames",
    },
    "export_files": {
        "source_validation_complete",
        "platform",
        "verified_on",
        "spec_url",
        "source_package",
        "source_validation",
        "source_validation_report",
        "frame_track",
        "track_validation",
        "track_report",
        "canvas",
        "resampling",
        "source_frame_count",
        "source_total_duration_ms",
        "frame_count",
        "total_duration_ms",
        "gif",
        "preview",
    },
}
FRAME_METRIC_FIELDS = {
    "size",
    "mode",
    "alpha_bbox",
    "transparent_pixels",
    "partial_alpha_pixels",
    "border_is_transparent",
    "pixel_sha256",
}


def _is_positive_int(value: object) -> bool:
    return type(value) is int and value > 0


def _is_nonnegative_int(value: object) -> bool:
    return type(value) is int and value >= 0


def _validate_sha256(value: object, label: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _validate_canvas(value: object, label: str) -> None:
    if not (
        isinstance(value, list)
        and len(value) == 2
        and all(_is_positive_int(item) for item in value)
    ):
        raise ValueError(f"{label} must contain two positive integers")


def _validate_exact_keys(
    value: object,
    expected: set[str],
    label: str,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    if set(value) != expected:
        raise ValueError(
            f"{label} must contain exactly: {', '.join(sorted(expected))}"
        )
    return value


def _validate_frame_metrics(
    value: object,
    frame_count: int,
    label: str,
) -> None:
    if not (
        isinstance(value, list)
        and len(value) == frame_count
        and all(isinstance(item, dict) for item in value)
    ):
        raise ValueError(f"{label} must contain one metric object per frame")
    for index, metric in enumerate(value):
        assert isinstance(metric, dict)
        _validate_exact_keys(
            metric,
            FRAME_METRIC_FIELDS,
            f"{label}[{index}]",
        )
        _validate_canvas(metric.get("size"), f"{label}[{index}].size")
        if metric.get("mode") != "RGBA":
            raise ValueError(f"{label}[{index}].mode must be 'RGBA'")
        alpha_bbox = metric.get("alpha_bbox")
        if alpha_bbox is not None and not (
            isinstance(alpha_bbox, list)
            and len(alpha_bbox) == 4
            and all(_is_nonnegative_int(item) for item in alpha_bbox)
        ):
            raise ValueError(
                f"{label}[{index}].alpha_bbox must be null or four integers"
            )
        if isinstance(alpha_bbox, list):
            width, height = metric["size"]
            left, top, right, bottom = alpha_bbox
            if not (left < right <= width and top < bottom <= height):
                raise ValueError(
                    f"{label}[{index}].alpha_bbox must stay inside the frame"
                )
        for field in ("transparent_pixels", "partial_alpha_pixels"):
            if not _is_nonnegative_int(metric.get(field)):
                raise ValueError(
                    f"{label}[{index}].{field} must be a non-negative integer"
                )
        pixel_count = int(metric["size"][0]) * int(metric["size"][1])
        if (
            int(metric["transparent_pixels"]) > pixel_count
            or int(metric["partial_alpha_pixels"]) > pixel_count
            or int(metric["transparent_pixels"])
            + int(metric["partial_alpha_pixels"])
            > pixel_count
        ):
            raise ValueError(
                f"{label}[{index}] alpha pixel counts exceed the frame size"
            )
        if not isinstance(metric.get("border_is_transparent"), bool):
            raise ValueError(
                f"{label}[{index}].border_is_transparent must be boolean"
            )
        _validate_sha256(
            metric.get("pixel_sha256"),
            f"{label}[{index}].pixel_sha256",
        )


def _validate_status_snapshot(value: object, label: str) -> None:
    snapshot = _validate_exact_keys(
        value,
        {"aggregate", "technical", "visual", "deliverable_ready"},
        label,
    )
    if snapshot.get("aggregate") not in {
        "technical_validation_failed",
        "visual_validation_failed",
        "pending_visual_validation",
        "pass",
    }:
        raise ValueError(f"{label}.aggregate is unsupported")
    if snapshot.get("technical") not in {"pass", "fail"}:
        raise ValueError(f"{label}.technical must be pass or fail")
    if snapshot.get("visual") not in {"pending", "pass", "fail"}:
        raise ValueError(f"{label}.visual must be pending, pass, or fail")
    if not isinstance(snapshot.get("deliverable_ready"), bool):
        raise ValueError(f"{label}.deliverable_ready must be boolean")
    expected_ready = (
        snapshot.get("aggregate") == "pass"
        and snapshot.get("technical") == "pass"
        and snapshot.get("visual") == "pass"
    )
    if snapshot.get("deliverable_ready") is not expected_ready:
        raise ValueError(f"{label}.deliverable_ready is inconsistent")


def _validate_common_contract(report: dict[str, object]) -> str:
    scope = report.get("artifact_scope")
    scope_fields = SCOPE_REPORT_FIELDS.get(str(scope))
    if scope_fields is None:
        raise ValueError("report.artifact_scope is unsupported")
    optional_fields = (
        {"output_validation_error"} if scope == "package_source" else set()
    )
    expected_fields = COMMON_REPORT_FIELDS | scope_fields
    missing = expected_fields - set(report)
    unexpected = set(report) - expected_fields - optional_fields
    if missing or unexpected:
        details = []
        if missing:
            details.append("missing " + ", ".join(sorted(missing)))
        if unexpected:
            details.append("unexpected " + ", ".join(sorted(unexpected)))
        raise ValueError(
            f"{scope} report fields are invalid: {'; '.join(details)}"
        )

    _validate_sha256(report.get("artifact_fingerprint"), "artifact_fingerprint")
    if not isinstance(report.get("deliverable_ready"), bool):
        raise ValueError("report.deliverable_ready must be boolean")
    if not isinstance(report.get("policy_overrides"), list):
        raise ValueError("report.policy_overrides must be an array")
    technical = _validate_exact_keys(
        report.get("technical_validation"),
        {"status", "checks"},
        "technical_validation",
    )
    checks = technical.get("checks")
    if not isinstance(checks, dict) or not checks:
        raise ValueError("technical_validation.checks must be non-empty")
    if technical.get("status") not in {"pass", "fail"}:
        raise ValueError("technical_validation.status must be pass or fail")
    if any(
        not isinstance(key, str) or not isinstance(value, bool)
        for key, value in checks.items()
    ):
        raise ValueError(
            "technical_validation.checks must map strings to booleans"
        )
    visual = _validate_exact_keys(
        report.get("visual_validation"),
        {"status", "required", "notes"},
        "visual_validation",
    )
    if visual.get("required") != list(NOTE_FIELDS):
        raise ValueError(
            "visual_validation.required must match the current review fields"
        )
    visual_status = visual.get("status")
    if visual_status not in {"pending", "pass", "fail"}:
        raise ValueError(
            "visual_validation.status must be pending, pass, or fail"
        )
    notes = visual.get("notes")
    if not isinstance(notes, dict):
        raise ValueError("visual_validation.notes must be an object")
    if visual_status == "pending":
        if notes:
            raise ValueError(
                "pending visual_validation.notes must be empty"
            )
    else:
        _validate_exact_keys(notes, set(NOTE_FIELDS), "visual_validation.notes")
        if any(
            not isinstance(notes[field], str) or not notes[field].strip()
            for field in NOTE_FIELDS
        ):
            raise ValueError(
                "completed visual_validation.notes values must be non-empty strings"
            )
    return str(scope)


def _validate_package_contract(report: dict[str, object]) -> None:
    _validate_canvas(report.get("canvas"), "package report canvas")
    frame_count = report.get("frame_count")
    if not _is_positive_int(frame_count):
        raise ValueError("package report frame_count must be positive")
    if not _is_positive_int(report.get("total_duration_ms")):
        raise ValueError("package report total_duration_ms must be positive")
    if report.get("resampling") not in {"lanczos", "nearest"}:
        raise ValueError("package report resampling is unsupported")
    encoding = _validate_exact_keys(
        report.get("webp_encoding"),
        {"lossless", "alpha_guard_applied"},
        "webp_encoding",
    )
    if any(not isinstance(value, bool) for value in encoding.values()):
        raise ValueError("webp_encoding values must be boolean")
    reference = _validate_exact_keys(
        report.get("reference"),
        {
            "filename",
            "sha256",
            "bytes",
            "format",
            "mode",
            "dimensions",
            "included_path",
        },
        "reference",
    )
    if not isinstance(reference.get("filename"), str) or not reference["filename"]:
        raise ValueError("reference.filename must be non-empty")
    _validate_sha256(reference.get("sha256"), "reference.sha256")
    if not _is_positive_int(reference.get("bytes")):
        raise ValueError("reference.bytes must be positive")
    for field in ("format", "mode"):
        if not isinstance(reference.get(field), str) or not reference[field]:
            raise ValueError(f"reference.{field} must be non-empty")
    _validate_canvas(reference.get("dimensions"), "reference.dimensions")
    if reference.get("included_path") is not None and not isinstance(
        reference.get("included_path"), str
    ):
        raise ValueError("reference.included_path must be a string or null")
    render_track = report.get("render_track")
    if render_track is not None:
        render_track = _validate_exact_keys(
            render_track,
            {"target_fps", "frame_count", "total_duration_ms"},
            "render_track",
        )
        if any(
            not _is_positive_int(render_track.get(field))
            for field in ("target_fps", "frame_count", "total_duration_ms")
        ):
            raise ValueError("render_track values must be positive integers")
    _validate_frame_metrics(
        report.get("frames"),
        int(frame_count),
        "package report frames",
    )
    if "output_validation_error" in report and (
        not isinstance(report.get("output_validation_error"), str)
        or not str(report["output_validation_error"]).strip()
    ):
        raise ValueError("output_validation_error must be non-empty")


def _validate_render_contract(report: dict[str, object]) -> None:
    for field in ("target_fps", "frame_count", "total_duration_ms"):
        if not _is_positive_int(report.get(field)):
            raise ValueError(f"render report {field} must be positive")
    _validate_frame_metrics(
        report.get("frames"),
        int(report["frame_count"]),
        "render report frames",
    )


def _validate_export_records(report: dict[str, object]) -> None:
    _validate_status_snapshot(report.get("source_validation"), "source_validation")
    track_validation = report.get("track_validation")
    if track_validation is not None:
        _validate_status_snapshot(track_validation, "track_validation")
    source_record = _validate_exact_keys(
        report.get("source_validation_report"),
        {"path", "sha256", "artifact_fingerprint"},
        "source_validation_report",
    )
    if not isinstance(source_record.get("path"), str) or not source_record["path"]:
        raise ValueError("source_validation_report.path must be non-empty")
    _validate_sha256(
        source_record.get("sha256"),
        "source_validation_report.sha256",
    )
    _validate_sha256(
        source_record.get("artifact_fingerprint"),
        "source_validation_report.artifact_fingerprint",
    )
    track_record = report.get("track_report")
    if track_record is not None:
        track_record = _validate_exact_keys(
            track_record,
            {"path", "sha256"},
            "track_report",
        )
        if not isinstance(track_record.get("path"), str) or not track_record["path"]:
            raise ValueError("track_report.path must be non-empty")
        _validate_sha256(track_record.get("sha256"), "track_report.sha256")


def _validate_gif_record(
    gif: dict[str, object],
    report: dict[str, object],
) -> None:
    if not isinstance(gif.get("path"), str) or not gif["path"]:
        raise ValueError("gif.path must be non-empty")
    if not _is_positive_int(gif.get("bytes")):
        raise ValueError("gif.bytes must be a positive integer")
    max_bytes = gif.get("max_bytes")
    if max_bytes is not None and not _is_positive_int(max_bytes):
        raise ValueError("gif.max_bytes must be null or a positive integer")
    colors = gif.get("colors")
    if type(colors) is not int or colors not in GIF_COLOR_CANDIDATES:
        raise ValueError("gif.colors must be a supported palette size")
    selected_fps = gif.get("selected_fps")
    if selected_fps is not None and not (
        type(selected_fps) is int and 1 <= selected_fps <= 100
    ):
        raise ValueError(
            "gif.selected_fps must be null or an integer from 1 to 100"
        )
    min_colors = gif.get("min_colors")
    if not (
        type(min_colors) is int
        and 1 <= min_colors <= 255
        and int(colors) >= min_colors
    ):
        raise ValueError(
            "gif.min_colors must be between 1 and the selected palette size"
        )
    alpha_threshold = gif.get("alpha_threshold")
    if not (
        type(alpha_threshold) is int and 1 <= alpha_threshold <= 254
    ):
        raise ValueError(
            "gif.alpha_threshold must be an integer from 1 to 254"
        )
    attempts = gif.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        raise ValueError("gif.attempts must be a non-empty array")
    for index, attempt in enumerate(attempts):
        attempt = _validate_exact_keys(
            attempt,
            {"fps", "colors", "bytes"},
            f"gif.attempts[{index}]",
        )
        fps = attempt.get("fps")
        if fps is not None and not (
            type(fps) is int and 1 <= fps <= 100
        ):
            raise ValueError(
                f"gif.attempts[{index}].fps must be null or 1 to 100"
            )
        attempt_colors = attempt.get("colors")
        if (
            type(attempt_colors) is not int
            or attempt_colors not in GIF_COLOR_CANDIDATES
            or int(attempt_colors) < int(min_colors)
        ):
            raise ValueError(
                f"gif.attempts[{index}].colors is inconsistent"
            )
        if not _is_positive_int(attempt.get("bytes")):
            raise ValueError(
                f"gif.attempts[{index}].bytes must be positive"
            )
    if attempts[-1] != {
        "fps": selected_fps,
        "colors": colors,
        "bytes": gif["bytes"],
    }:
        raise ValueError(
            "gif selected settings must match the final export attempt"
        )
    _validate_sha256(gif.get("sha256"), "gif.sha256")

    validation = _validate_exact_keys(
        gif.get("validation"),
        {
            "encoded_frame_count",
            "durations_ms",
            "total_duration_ms",
        },
        "gif.validation",
    )
    encoded_frame_count = validation.get("encoded_frame_count")
    if not _is_positive_int(encoded_frame_count):
        raise ValueError(
            "gif.validation.encoded_frame_count must be positive"
        )
    durations = validation.get("durations_ms")
    if not (
        isinstance(durations, list)
        and len(durations) == encoded_frame_count
        and all(_is_positive_int(value) for value in durations)
    ):
        raise ValueError(
            "gif.validation.durations_ms must contain one positive duration "
            "per encoded frame"
        )
    validation_total = validation.get("total_duration_ms")
    if (
        not _is_positive_int(validation_total)
        or validation_total != sum(durations)
    ):
        raise ValueError(
            "gif.validation.total_duration_ms must equal its durations"
        )
    if abs(int(validation_total) - int(report["total_duration_ms"])) > 10:
        raise ValueError(
            "gif.validation duration must match the exported timeline"
        )


def _validate_preview_record(
    preview: dict[str, object],
    report: dict[str, object],
) -> None:
    if not isinstance(preview.get("path"), str) or not preview["path"]:
        raise ValueError("preview.path must be non-empty")
    frame = preview.get("frame")
    if not _is_positive_int(frame):
        raise ValueError("preview.frame must be a positive integer")
    frame_source = preview.get("frame_source")
    if frame_source not in {"authored", "exported"}:
        raise ValueError(
            "preview.frame_source must be 'authored' or 'exported'"
        )
    if frame_source == "exported" and int(frame) > int(report["frame_count"]):
        raise ValueError("preview.frame is outside the exported timeline")
    mode = preview.get("mode")
    if mode not in {"rgba", "indexed"}:
        raise ValueError("preview.mode must be 'rgba' or 'indexed'")
    colors = preview.get("colors")
    if mode == "rgba":
        if colors is not None:
            raise ValueError("rgba preview.colors must be null")
    elif type(colors) is not int or colors not in PREVIEW_COLOR_CANDIDATES:
        raise ValueError(
            "indexed preview.colors must be a supported palette size"
        )
    if not _is_positive_int(preview.get("bytes")):
        raise ValueError("preview.bytes must be a positive integer")
    max_bytes = preview.get("max_bytes")
    if max_bytes is not None and not _is_positive_int(max_bytes):
        raise ValueError(
            "preview.max_bytes must be null or a positive integer"
        )
    _validate_sha256(preview.get("sha256"), "preview.sha256")


def _validate_export_contract(report: dict[str, object]) -> None:
    _validate_canvas(report.get("canvas"), "export report canvas")
    if report.get("resampling") not in {"lanczos", "nearest"}:
        raise ValueError("export report resampling is unsupported")
    for field in (
        "source_frame_count",
        "source_total_duration_ms",
        "frame_count",
        "total_duration_ms",
    ):
        if not _is_positive_int(report.get(field)):
            raise ValueError(f"export report {field} must be positive")
    if not isinstance(report.get("source_validation_complete"), bool):
        raise ValueError("source_validation_complete must be boolean")
    for field in (
        "platform",
        "verified_on",
        "spec_url",
        "source_package",
    ):
        if not isinstance(report.get(field), str) or not report[field]:
            raise ValueError(f"export report {field} must be non-empty")
    if report.get("frame_track") not in {"keyframes", "render"}:
        raise ValueError(
            "export report frame_track must be 'keyframes' or 'render'"
        )
    _validate_export_records(report)
    gif = _validate_exact_keys(
        report.get("gif"),
        {
            "path",
            "bytes",
            "max_bytes",
            "colors",
            "selected_fps",
            "min_colors",
            "attempts",
            "alpha_threshold",
            "sha256",
            "validation",
        },
        "gif",
    )
    _validate_gif_record(gif, report)
    preview = report.get("preview")
    if preview is not None:
        preview = _validate_exact_keys(
            preview,
            {
                "path",
                "frame",
                "frame_source",
                "mode",
                "colors",
                "bytes",
                "max_bytes",
                "sha256",
            },
            "preview",
        )
        _validate_preview_record(preview, report)
        if preview.get("path") == gif.get("path"):
            raise ValueError("GIF and preview paths must be distinct")


def validate_report_contract(report: dict[str, object]) -> None:
    scope = _validate_common_contract(report)
    if scope == "package_source":
        _validate_package_contract(report)
    elif scope == "render_track":
        _validate_render_contract(report)
    else:
        _validate_export_contract(report)
