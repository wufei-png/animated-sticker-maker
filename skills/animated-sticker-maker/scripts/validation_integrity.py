#!/usr/bin/env python3
"""Validate report evidence, state transitions, and upstream dependencies."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image

from artifact_integrity import (
    package_fingerprint,
    render_track_fingerprint,
    report_artifact_fingerprint,
    safe_relative_file,
    sha256_path,
)
from motion_schema import validate_motion
from validation_evidence import (
    gif_encoding_evidence,
    package_webp_alpha_guard_required,
    package_source_evidence,
    render_track_evidence,
    validate_export_gif_evidence,
    validate_preview_evidence,
)
from validation_schema import (
    GIF_CHECK_FIELDS,
    NOTE_FIELDS,
    validate_report_contract,
)


REPORT_SCHEMA_VERSION = 1
PACKAGE_SOURCE_CHECK_IDS = {
    "frame_count_in_default_range",
    "source_frames_are_rgba",
    "all_frames_match_expected_size",
    "all_borders_transparent",
    "all_frames_have_visible_pixels",
    "all_frames_are_unique",
    "duration_in_default_range",
}
PACKAGE_WEBP_CHECK_IDS = {
    "sticker_is_webp",
    "sticker_matches_expected_size",
    "sticker_frame_count_matches_source",
    "sticker_loop_matches_motion",
    "sticker_transparency_preserved",
    "sticker_durations_match_source",
}
RENDER_TRACK_CHECK_IDS = {
    "frame_count_matches_ordered_entries",
    "duration_count_matches_frames",
    "total_duration_matches_authored_keyframes",
    "target_fps_matches_timeline",
    "source_frames_are_rgba",
    "all_frames_match_expected_size",
    "all_borders_transparent",
    "all_frames_have_visible_pixels",
}
EXPORT_GIF_CHECK_IDS = set(GIF_CHECK_FIELDS)
PLATFORM_PATTERN = re.compile(r"[A-Za-z0-9._-]+")
PACKAGE_POLICY_OVERRIDES = {
    "frame_count_in_default_range": {
        "source": "--allow-nonstandard-frame-count",
        "actual_field": "frame_count",
        "default_range": [4, 8],
    },
    "duration_in_default_range": {
        "source": "--allow-nonstandard-timing",
        "actual_field": "total_duration_ms",
        "default_range": [1200, 2000],
    },
}


def validate_report_schema(report: dict[str, object]) -> None:
    schema_version = report.get("schema_version")
    if type(schema_version) is not int or schema_version != REPORT_SCHEMA_VERSION:
        raise ValueError(
            f"report.schema_version must be {REPORT_SCHEMA_VERSION}; "
            "regenerate the package or export with the current Skill"
        )


def validation_status(report: dict[str, object]) -> dict[str, object]:
    technical = report.get("technical_validation")
    visual = report.get("visual_validation")
    return {
        "aggregate": report.get("status") if isinstance(report.get("status"), str) else None,
        "technical": technical.get("status") if isinstance(technical, dict) else None,
        "visual": visual.get("status") if isinstance(visual, dict) else None,
        "deliverable_ready": report.get("deliverable_ready") is True,
    }


def _validated_policy_overrides(
    report: dict[str, object],
    checks: dict[str, bool],
) -> set[str]:
    overrides = report.get("policy_overrides")
    if not isinstance(overrides, list):
        raise ValueError("report.policy_overrides must be an array")
    if report.get("artifact_scope") != "package_source" and overrides:
        raise ValueError(
            "only package_source reports may declare policy_overrides"
        )

    overridden_checks: set[str] = set()
    for index, override in enumerate(overrides):
        if not isinstance(override, dict):
            raise ValueError(f"policy_overrides[{index}] must be an object")
        if set(override) != {
            "check_id",
            "source",
            "actual",
            "default_range",
        }:
            raise ValueError(
                f"policy_overrides[{index}] must contain check_id, source, "
                "actual, and default_range"
            )
        check_id = override.get("check_id")
        if check_id not in PACKAGE_POLICY_OVERRIDES:
            raise ValueError(
                f"policy_overrides[{index}].check_id is not overridable"
            )
        if check_id in overridden_checks:
            raise ValueError("policy_overrides check_id values must be unique")
        specification = PACKAGE_POLICY_OVERRIDES[str(check_id)]
        if override.get("source") != specification["source"]:
            raise ValueError(
                f"policy_overrides[{index}].source must be "
                f"{specification['source']!r}"
            )
        if override.get("default_range") != specification["default_range"]:
            raise ValueError(
                f"policy_overrides[{index}].default_range is inconsistent"
            )
        actual = report.get(str(specification["actual_field"]))
        if override.get("actual") != actual:
            raise ValueError(
                f"policy_overrides[{index}].actual does not match report metadata"
            )
        default_min, default_max = specification["default_range"]
        if (
            not isinstance(actual, int)
            or isinstance(actual, bool)
            or default_min <= actual <= default_max
        ):
            raise ValueError(
                f"policy_overrides[{index}] does not describe a real deviation"
            )
        if checks.get(str(check_id)) is not False:
            raise ValueError(
                f"policy_overrides[{index}] must bind a failed objective check"
            )
        overridden_checks.add(str(check_id))
    return overridden_checks


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
    typed_checks = {str(key): value for key, value in checks.items()}
    overridden_checks = _validated_policy_overrides(report, typed_checks)
    expected = (
        "pass"
        if all(
            passed or check_id in overridden_checks
            for check_id, passed in typed_checks.items()
        )
        else "fail"
    )
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
    validate_report_schema(report)
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


def _validate_technical_evidence(
    report_path: Path,
    report: dict[str, object],
) -> dict[str, bool]:
    technical = report.get("technical_validation")
    if not isinstance(technical, dict):
        raise ValueError("report.technical_validation must be an object")
    checks = technical.get("checks")
    if not isinstance(checks, dict) or not checks:
        raise ValueError("technical_validation.checks must be a non-empty object")
    if any(not isinstance(value, bool) for value in checks.values()):
        raise ValueError("every technical_validation check must be boolean")
    typed_checks = {str(key): value for key, value in checks.items()}
    scope = report.get("artifact_scope")
    if scope == "package_source":
        package = report_path.parent.parent
        motion = validate_motion(
            _load_json_object(package / "source" / "motion.json", "packaged motion"),
            packaged=True,
        )
        expected = PACKAGE_SOURCE_CHECK_IDS | PACKAGE_WEBP_CHECK_IDS
        if isinstance(motion.get("render"), dict):
            expected = expected | {"render_track_technical_validation_pass"}
        if technical.get("status") == "pass":
            if set(typed_checks) != expected:
                raise ValueError(
                    "package technical_validation.checks must exactly match "
                    "the package evidence contract"
                )
        else:
            allowed = expected | {"sticker_is_readable"}
            if not PACKAGE_SOURCE_CHECK_IDS.issubset(typed_checks) or not set(
                typed_checks
            ).issubset(allowed):
                raise ValueError(
                    "failed package technical_validation.checks do not match "
                    "the package evidence contract"
                )
        inspect_sticker = bool(
            set(typed_checks) & (PACKAGE_WEBP_CHECK_IDS | {"sticker_is_readable"})
        )
        (
            actual_checks,
            actual_metrics,
            _,
            _,
        ) = package_source_evidence(
            package,
            motion,
            inspect_sticker=inspect_sticker,
        )
        # The package contains normalized RGBA PNGs, so the original input mode
        # recorded during packaging cannot be reconstructed from the artifact.
        actual_checks["source_frames_are_rgba"] = typed_checks[
            "source_frames_are_rgba"
        ]
        if typed_checks != actual_checks:
            raise ValueError(
                "package technical_validation.checks do not match current media"
            )
        if report.get("frames") != actual_metrics:
            raise ValueError(
                "package report frames do not match current packaged frames"
            )
        frames = motion["frames"]
        frame_count = len(frames)
        total_duration_ms = sum(
            int(frame["duration_ms"])
            for frame in frames
        )
        for field, actual in (
            ("frame_count", frame_count),
            ("total_duration_ms", total_duration_ms),
        ):
            recorded = report.get(field)
            if type(recorded) is not int or recorded != actual:
                raise ValueError(
                    f"package report {field} must match the packaged motion"
                )
        expected_metadata = {
            "canvas": motion["canvas"],
            "resampling": motion["resampling"],
        }
        for field, expected_value in expected_metadata.items():
            if report.get(field) != expected_value:
                raise ValueError(
                    f"package report {field} must match the packaged motion"
                )
        reference = _load_json_object(
            package / "source" / "reference.json",
            "reference metadata",
        )
        if report.get("reference") != reference:
            raise ValueError(
                "package report reference must match source/reference.json"
            )
        motion_reference = motion.get("reference")
        if not isinstance(motion_reference, dict) or any(
            motion_reference.get(field) != reference.get(field)
            for field in ("filename", "sha256", "included_path")
        ):
            raise ValueError(
                "packaged motion reference must match source/reference.json"
            )
        included_path = reference.get("included_path")
        if included_path is not None:
            included = safe_relative_file(
                package / "source",
                included_path,
                "reference.included_path",
            )
            if reference.get("sha256") != sha256_path(included):
                raise ValueError(
                    "reference.sha256 does not match the included reference"
                )
            if reference.get("bytes") != included.stat().st_size:
                raise ValueError(
                    "reference.bytes does not match the included reference"
                )
            with Image.open(included) as image:
                image.load()
                included_metadata = {
                    "format": image.format,
                    "mode": image.mode,
                    "dimensions": list(image.size),
                }
            if any(
                reference.get(field) != value
                for field, value in included_metadata.items()
            ):
                raise ValueError(
                    "reference media metadata does not match the included file"
                )
        overrides = report.get("policy_overrides")
        overridden_checks = {
            str(override["check_id"])
            for override in overrides
            if isinstance(override, dict)
            and isinstance(override.get("check_id"), str)
        }
        pre_encoding_checks = {
            key: value
            for key, value in actual_checks.items()
            if key not in PACKAGE_WEBP_CHECK_IDS
            and key != "sticker_is_readable"
        }
        pre_encoding_pass = all(
            passed or check_id in overridden_checks
            for check_id, passed in pre_encoding_checks.items()
        )
        expected_encoding = {
            "lossless": motion["resampling"] == "nearest",
            "alpha_guard_applied": bool(
                pre_encoding_pass
                and package_webp_alpha_guard_required(package, motion)
            ),
        }
        if report.get("webp_encoding") != expected_encoding:
            raise ValueError(
                "package report webp_encoding does not match current source media"
            )
        render = motion.get("render")
        expected_render_summary = None
        if isinstance(render, dict):
            render_frames = render["frames"]
            expected_render_summary = {
                "target_fps": render["target_fps"],
                "frame_count": len(render_frames),
                "total_duration_ms": sum(
                    int(frame["duration_ms"])
                    for frame in render_frames
                ),
            }
        if report.get("render_track") != expected_render_summary:
            raise ValueError(
                "package report render_track must match the packaged motion"
            )
    elif scope == "render_track":
        if set(typed_checks) != RENDER_TRACK_CHECK_IDS:
            raise ValueError(
                "render technical_validation.checks must exactly match "
                "the render-track evidence contract"
            )
        package = report_path.parent.parent
        motion = validate_motion(
            _load_json_object(package / "source" / "motion.json", "packaged motion"),
            packaged=True,
        )
        render = motion.get("render")
        if not isinstance(render, dict):
            raise ValueError("render report requires packaged render metadata")
        render_frames = render["frames"]
        actual_checks, actual_metrics = render_track_evidence(package, motion)
        actual_checks["source_frames_are_rgba"] = typed_checks[
            "source_frames_are_rgba"
        ]
        if typed_checks != actual_checks:
            raise ValueError(
                "render technical_validation.checks do not match current media"
            )
        if report.get("frames") != actual_metrics:
            raise ValueError(
                "render report frames do not match current render media"
            )
        expected_metadata = {
            "target_fps": render["target_fps"],
            "frame_count": len(render_frames),
            "total_duration_ms": sum(
                int(frame["duration_ms"])
                for frame in render_frames
            ),
        }
        if any(
            report.get(field) != value
            for field, value in expected_metadata.items()
        ):
            raise ValueError(
                "render report metadata must match the packaged motion"
            )
    elif scope == "export_files":
        if set(typed_checks) != EXPORT_GIF_CHECK_IDS:
            raise ValueError(
                "export technical_validation.checks must exactly match "
                "the GIF evidence contract"
            )
    else:
        raise ValueError(
            "report artifact_scope must be 'package_source', "
            "'render_track', or 'export_files'"
        )
    return typed_checks


def _validate_export_metadata(
    report_path: Path,
    report: dict[str, object],
    motion: dict[str, object],
) -> None:
    platform = report.get("platform")
    if (
        not isinstance(platform, str)
        or not PLATFORM_PATTERN.fullmatch(platform)
        or platform in {".", ".."}
    ):
        raise ValueError("export report platform must be one safe path segment")
    if platform != report_path.parent.name:
        raise ValueError("export report platform must match its export directory")

    spec_url = report.get("spec_url")
    parsed_spec = urlparse(spec_url) if isinstance(spec_url, str) else None
    if (
        parsed_spec is None
        or parsed_spec.scheme not in {"http", "https"}
        or not parsed_spec.netloc
    ):
        raise ValueError("export report spec_url must be an absolute http(s) URL")

    verified_on = report.get("verified_on")
    if not isinstance(verified_on, str):
        raise ValueError("export report verified_on must be an ISO date")
    try:
        verified_date = date.fromisoformat(verified_on)
    except ValueError as exc:
        raise ValueError("export report verified_on must be an ISO date") from exc
    if verified_date > date.today():
        raise ValueError("export report verified_on cannot be in the future")
    if verified_on != verified_date.isoformat():
        raise ValueError("export report verified_on must use YYYY-MM-DD form")

    if report.get("resampling") != motion.get("resampling"):
        raise ValueError("export report resampling must match the source motion")

    gif = report.get("gif")
    if not isinstance(gif, dict):
        raise ValueError("export report must declare a gif object")
    gif_bytes = gif.get("bytes")
    if (
        not isinstance(gif_bytes, int)
        or isinstance(gif_bytes, bool)
        or gif_bytes <= 0
    ):
        raise ValueError("export report gif.bytes must be a positive integer")
    max_bytes = gif.get("max_bytes")
    if max_bytes is not None and (
        not isinstance(max_bytes, int)
        or isinstance(max_bytes, bool)
        or max_bytes <= 0
    ):
        raise ValueError("export report gif.max_bytes must be null or positive")

    preview = report.get("preview")
    if isinstance(preview, dict):
        preview_bytes = preview.get("bytes")
        if (
            not isinstance(preview_bytes, int)
            or isinstance(preview_bytes, bool)
            or preview_bytes <= 0
        ):
            raise ValueError("export report preview.bytes must be a positive integer")
        preview_max_bytes = preview.get("max_bytes")
        if preview_max_bytes is not None and (
            not isinstance(preview_max_bytes, int)
            or isinstance(preview_max_bytes, bool)
            or preview_max_bytes <= 0
        ):
            raise ValueError(
                "export report preview.max_bytes must be null or positive"
            )


def validate_report_binding(report_path: Path, report: dict[str, object]) -> None:
    validate_report_schema(report)
    _validated_technical_status(report)
    validate_report_contract(report)
    technical_checks = _validate_technical_evidence(report_path, report)
    expected = report.get("artifact_fingerprint")
    if not isinstance(expected, str):
        raise ValueError("report has no artifact fingerprint")
    if report_artifact_fingerprint(report_path, report) != expected:
        raise ValueError("validation artifacts changed; regenerate the report")

    if report.get("artifact_scope") != "export_files":
        return
    gif = report.get("gif")
    if not isinstance(gif, dict) or not isinstance(gif.get("path"), str):
        raise ValueError("export report must declare gif.path")
    if Path(str(gif["path"])).suffix.lower() != ".gif":
        raise ValueError("export report gif.path must end in .gif")
    gif_path = safe_relative_file(
        report_path.parent,
        gif["path"],
        "gif.path",
    )
    if gif.get("sha256") != sha256_path(gif_path):
        raise ValueError("export report gif.sha256 does not match its file")
    gif_size = gif_path.stat().st_size
    if gif.get("bytes") != gif_size:
        raise ValueError("export report gif.bytes does not match its file")
    gif_max_bytes = gif.get("max_bytes")
    if isinstance(gif_max_bytes, int) and gif_size > gif_max_bytes:
        raise ValueError("exported GIF exceeds gif.max_bytes")

    preview = report.get("preview")
    preview_path = None
    if preview is not None:
        if not isinstance(preview, dict) or not isinstance(preview.get("path"), str):
            raise ValueError("export report preview must declare preview.path")
        if Path(str(preview["path"])).suffix.lower() != ".png":
            raise ValueError("export report preview.path must end in .png")
        if preview["path"] == gif["path"]:
            raise ValueError("export GIF and preview paths must be distinct")
        preview_path = safe_relative_file(
            report_path.parent,
            preview["path"],
            "preview.path",
        )
        if preview.get("sha256") != sha256_path(preview_path):
            raise ValueError("export report preview.sha256 does not match its file")
        preview_size = preview_path.stat().st_size
        if preview.get("bytes") != preview_size:
            raise ValueError("export report preview.bytes does not match its file")
        preview_max_bytes = preview.get("max_bytes")
        if (
            isinstance(preview_max_bytes, int)
            and preview_size > preview_max_bytes
        ):
            raise ValueError("exported preview exceeds preview.max_bytes")
    package = report_path.parent.parent.parent.resolve()
    motion = validate_motion(
        _load_json_object(package / "source" / "motion.json", "packaged motion"),
        packaged=True,
    )
    _validate_export_metadata(report_path, report, motion)
    gif_validation = gif.get("validation")
    actual_gif_validation = validate_export_gif_evidence(
        gif_path,
        report,
        motion,
    )
    if gif_validation != gif_encoding_evidence(actual_gif_validation):
        raise ValueError(
            "export report gif.validation does not match current GIF media"
        )
    if actual_gif_validation.get("checks") != technical_checks:
        raise ValueError(
            "export technical_validation.checks do not match current GIF media"
        )
    if isinstance(preview, dict) and preview_path is not None:
        preview_frame = int(preview["frame"])
        preview_limit = (
            len(motion["frames"])
            if preview["frame_source"] == "authored"
            else int(report["frame_count"])
        )
        if preview_frame > preview_limit:
            raise ValueError(
                "export report preview.frame is outside its declared source"
            )
        validate_preview_evidence(
            preview_path,
            preview,
            (int(report["canvas"][0]), int(report["canvas"][1])),
        )
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
    if source_report.get("artifact_scope") != "package_source":
        raise ValueError("source validation report must use package_source scope")
    validate_report_binding(source_report_path, source_report)
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
    if track_report.get("artifact_scope") != "render_track":
        raise ValueError("render-track report must use render_track scope")
    validate_report_binding(track_path, track_report)
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
