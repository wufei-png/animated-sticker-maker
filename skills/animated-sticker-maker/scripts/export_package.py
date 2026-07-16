#!/usr/bin/env python3
"""Load validated package frame tracks and derive export previews."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from artifact_integrity import (
    package_fingerprint,
    render_track_fingerprint,
    safe_relative_file,
)
from gif_export_core import fit_frame
from motion_schema import is_positive_int, validate_motion
from validation_integrity import (
    validate_report_binding,
    validate_report_state,
)


def load_validated_package(
    package: Path,
    allow_unvalidated: bool,
    frame_track: str = "keyframes",
    track_report: Path | None = None,
) -> tuple[
    list[Image.Image],
    list[int],
    dict[str, object],
    dict[str, object],
    dict[str, object] | None,
]:
    motion_path = package / "source" / "motion.json"
    report_path = package / "validation" / "report.json"
    frames_dir = package / "source" / "frames"
    if (
        not motion_path.is_file()
        or not report_path.is_file()
        or not frames_dir.is_dir()
    ):
        raise FileNotFoundError(
            "package must contain source/motion.json, source/frames, and "
            "validation/report.json"
        )

    motion = validate_motion(
        json.loads(motion_path.read_text(encoding="utf-8")),
        packaged=True,
    )
    entries = motion["frames"]
    assert isinstance(entries, list)
    durations = [
        entry.get("duration_ms") for entry in entries if isinstance(entry, dict)
    ]
    if len(durations) != len(entries) or not all(
        is_positive_int(value) for value in durations
    ):
        raise ValueError(
            "every motion frame must have a positive integer duration_ms"
        )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    expected_fingerprint = report.get("artifact_fingerprint")
    if report.get("artifact_scope") != "package_source" or not isinstance(
        expected_fingerprint, str
    ):
        raise ValueError(
            "package validation report has no bound source artifact fingerprint"
        )
    validate_report_binding(report_path, report)
    actual_fingerprint = package_fingerprint(package)
    if actual_fingerprint != expected_fingerprint:
        raise ValueError(
            "package source changed after validation; repack and repeat validation"
        )
    source_validation = validate_report_state(report)
    validation_complete = source_validation["deliverable_ready"] is True
    if not validation_complete and not allow_unvalidated:
        raise ValueError(
            "package validation is incomplete "
            f"(aggregate={source_validation['aggregate']!r}, "
            f"technical={source_validation['technical']!r}, "
            f"visual={source_validation['visual']!r}); pass both validations first "
            "or use --allow-unvalidated explicitly"
        )

    derived_validation = None
    if frame_track == "keyframes":
        frame_paths = [
            safe_relative_file(
                package / "source",
                entry.get("file") if isinstance(entry, dict) else None,
                f"frames[{index}].file",
            )
            for index, entry in enumerate(entries)
        ]
    elif frame_track == "render":
        render = motion.get("render")
        if not isinstance(render, dict):
            raise ValueError("source/motion.json has no render track metadata")
        render_entries = render["frames"]
        assert isinstance(render_entries, list)
        frame_paths = [
            safe_relative_file(
                package / "source",
                entry.get("file") if isinstance(entry, dict) else None,
                f"render.frames[{index}].file",
            )
            for index, entry in enumerate(render_entries)
        ]
        durations = [int(entry["duration_ms"]) for entry in render_entries]
        if track_report is None:
            if not allow_unvalidated:
                raise ValueError(
                    "render track export requires --track-report with aggregate, "
                    "technical/checks, and visual pass states"
                )
        else:
            derived_report = json.loads(track_report.read_text(encoding="utf-8"))
            expected_track_fingerprint = derived_report.get(
                "artifact_fingerprint"
            )
            if derived_report.get(
                "artifact_scope"
            ) != "render_track" or not isinstance(
                expected_track_fingerprint, str
            ):
                raise ValueError(
                    "render-track validation has no bound artifact fingerprint"
                )
            validate_report_binding(track_report, derived_report)
            if render_track_fingerprint(package) != expected_track_fingerprint:
                raise ValueError(
                    "render track changed after validation; regenerate and repeat "
                    "its validation"
                )
            derived_validation = validate_report_state(derived_report)
            derived_complete = derived_validation["deliverable_ready"] is True
            if not derived_complete and not allow_unvalidated:
                raise ValueError(
                    "render track validation is incomplete "
                    f"({derived_validation}); pass its technical and visual "
                    "validations first"
                )
    else:
        raise ValueError(f"unsupported frame track: {frame_track}")

    frames: list[Image.Image] = []
    for path in frame_paths:
        with Image.open(path) as source:
            frames.append(source.convert("RGBA"))
    return frames, durations, motion, source_validation, derived_validation


def automatic_preview_frame(
    package: Path,
    motion: dict[str, object],
    size: tuple[int, int],
    resampling: str = "lanczos",
) -> tuple[Image.Image, int]:
    entries = motion.get("frames")
    assert isinstance(entries, list) and entries
    preview_index = max(
        range(len(entries)),
        key=lambda index: int(entries[index]["duration_ms"]),
    )
    semantic_hold = motion.get("semantic_hold_frame")
    if isinstance(semantic_hold, str) and semantic_hold:
        relative = Path(semantic_hold)
        if not relative.is_absolute() and ".." not in relative.parts:
            candidate = package / "source" / relative
            if candidate.is_file() and candidate.resolve().is_relative_to(
                (package / "source").resolve()
            ):
                semantic_name = relative.as_posix()
                for index, entry in enumerate(entries):
                    if entry.get("file") == semantic_name:
                        preview_index = index
                        with Image.open(candidate) as source:
                            return (
                                fit_frame(
                                    source.convert("RGBA"),
                                    size,
                                    resampling,
                                ),
                                preview_index,
                            )
                raise ValueError(
                    "semantic_hold_frame must match one authored keyframe entry"
                )
    keyframes = sorted((package / "source/frames").glob("*.png"))
    if len(keyframes) != len(entries):
        raise ValueError(
            "cannot resolve automatic preview from package keyframes"
        )
    with Image.open(keyframes[preview_index]) as source:
        return (
            fit_frame(source.convert("RGBA"), size, resampling),
            preview_index,
        )
