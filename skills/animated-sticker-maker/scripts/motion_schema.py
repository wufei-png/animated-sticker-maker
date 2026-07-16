#!/usr/bin/env python3
"""Validate the portable motion-plan contract shared by package tools."""

from __future__ import annotations

import re
from pathlib import Path


SCHEMA_VERSION = 2
MAX_RENDER_FRAMES = 240
MAX_RENDER_PIXELS = 64 * 1024 * 1024
RESAMPLING_POLICIES = {"lanczos", "nearest"}
WORK_COLOR_PATTERN = re.compile(r"#[0-9A-Fa-f]{6}")
LEGACY_RENDER_FIELDS = {
    "frame_dir",
    "frame_count",
    "frame_durations_ms",
    "total_duration_ms",
}


def is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def require_nonempty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def validate_relative_path(value: object, label: str) -> str:
    text = require_nonempty_string(value, label)
    relative = Path(text)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} must be a safe relative path")
    return text


def validate_string_list(value: object, label: str, *, nonempty: bool = False) -> None:
    if not isinstance(value, list) or (nonempty and not value):
        qualifier = "a non-empty" if nonempty else "an"
        raise ValueError(f"{label} must be {qualifier} array of non-empty strings")
    for index, item in enumerate(value):
        require_nonempty_string(item, f"{label}[{index}]")


def validate_frame_entries(value: object, label: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty array")
    entries: list[dict[str, object]] = []
    for index, frame in enumerate(value):
        if not isinstance(frame, dict):
            raise ValueError(f"{label}[{index}] must be an object")
        validate_relative_path(frame.get("file"), f"{label}[{index}].file")
        if not is_positive_int(frame.get("duration_ms")):
            raise ValueError(f"{label}[{index}].duration_ms must be a positive integer")
        entries.append(frame)
    return entries


def validate_render_pixel_budget(aggregate_pixels: int) -> int:
    if not is_positive_int(aggregate_pixels):
        raise ValueError("render aggregate input pixels must be a positive integer")
    if aggregate_pixels > MAX_RENDER_PIXELS:
        raise ValueError("motion.render.frames exceed the 64M aggregate input-pixel limit")
    return aggregate_pixels


def validate_motion(motion: object, *, packaged: bool) -> dict[str, object]:
    if not isinstance(motion, dict):
        raise ValueError("motion.json must contain a JSON object")
    if motion.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"motion.schema_version must be {SCHEMA_VERSION}")

    require_nonempty_string(motion.get("id"), "motion.id")
    require_nonempty_string(motion.get("prompt"), "motion.prompt")
    if packaged:
        if "reference_image" in motion:
            raise ValueError(
                "packaged motion must use motion.reference instead of reference_image"
            )
        reference = motion.get("reference")
        if not isinstance(reference, dict):
            raise ValueError("motion.reference must be an object in a packaged motion plan")
        require_nonempty_string(reference.get("filename"), "motion.reference.filename")
        sha256 = require_nonempty_string(reference.get("sha256"), "motion.reference.sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError("motion.reference.sha256 must be a lowercase SHA-256 digest")
        included_path = reference.get("included_path")
        if included_path is not None:
            validate_relative_path(included_path, "motion.reference.included_path")
    else:
        if "reference" in motion:
            raise ValueError(
                "working motion must use motion.reference_image instead of reference"
            )
        require_nonempty_string(motion.get("reference_image"), "motion.reference_image")

    canvas = motion.get("canvas")
    if not (
        isinstance(canvas, list)
        and len(canvas) == 2
        and all(is_positive_int(value) for value in canvas)
    ):
        raise ValueError("motion.canvas must contain two positive integers")
    if not isinstance(motion.get("loop"), bool):
        raise ValueError("motion.loop must be a boolean")
    if motion.get("resampling") not in RESAMPLING_POLICIES:
        raise ValueError("motion.resampling must be 'lanczos' or 'nearest'")

    identity_lock = motion.get("identity_lock")
    if not isinstance(identity_lock, dict):
        raise ValueError("motion.identity_lock must be an object")
    require_nonempty_string(identity_lock.get("subject"), "motion.identity_lock.subject")
    validate_string_list(identity_lock.get("fixed"), "motion.identity_lock.fixed", nonempty=True)
    validate_string_list(identity_lock.get("flexible"), "motion.identity_lock.flexible")
    validate_string_list(identity_lock.get("forbidden"), "motion.identity_lock.forbidden")

    generation_plan = motion.get("generation_plan")
    if not isinstance(generation_plan, dict):
        raise ValueError("motion.generation_plan must be an object")
    validate_string_list(generation_plan.get("anchors"), "motion.generation_plan.anchors")
    validate_string_list(
        generation_plan.get("deterministic"),
        "motion.generation_plan.deterministic",
    )

    transparency = motion.get("transparency")
    if not isinstance(transparency, dict):
        raise ValueError("motion.transparency must be an object")
    strategy = transparency.get("strategy")
    if strategy not in {"existing-alpha", "chroma-key"}:
        raise ValueError(
            "motion.transparency.strategy must be 'existing-alpha' or 'chroma-key'"
        )
    work_color = transparency.get("work_color")
    if "work_color" not in transparency:
        raise ValueError("motion.transparency.work_color must be present")
    if strategy == "existing-alpha":
        if work_color is not None:
            raise ValueError("motion.transparency.work_color must be null for existing-alpha")
    elif not isinstance(work_color, str) or not WORK_COLOR_PATTERN.fullmatch(work_color):
        raise ValueError(
            "motion.transparency.work_color must be a #RRGGBB color for chroma-key"
        )

    frames = validate_frame_entries(motion.get("frames"), "motion.frames")
    for index, frame in enumerate(frames):
        require_nonempty_string(frame.get("description"), f"motion.frames[{index}].description")
        if packaged:
            expected_path = f"frames/{index:03d}.png"
            if frame.get("file") != expected_path:
                raise ValueError(
                    f"packaged motion.frames[{index}].file must be {expected_path!r}"
                )

    semantic_hold = motion.get("semantic_hold_frame")
    if semantic_hold is not None:
        validate_relative_path(semantic_hold, "motion.semantic_hold_frame")

    render = motion.get("render")
    if render is not None:
        if not isinstance(render, dict):
            raise ValueError("motion.render must be an object")
        legacy_fields = sorted(LEGACY_RENDER_FIELDS.intersection(render))
        if legacy_fields:
            raise ValueError(
                "motion.render contains removed schema v1 fields: "
                + ", ".join(legacy_fields)
            )
        target_fps = render.get("target_fps")
        if not is_positive_int(target_fps) or target_fps > 100:
            raise ValueError("motion.render.target_fps must be an integer from 1 to 100")
        render_frames = validate_frame_entries(render.get("frames"), "motion.render.frames")
        if len(render_frames) > MAX_RENDER_FRAMES:
            raise ValueError(
                f"motion.render.frames may contain at most {MAX_RENDER_FRAMES} frames"
            )
        if packaged:
            for index, frame in enumerate(render_frames):
                expected_path = f"rendered-frames/{index:04d}.png"
                if frame.get("file") != expected_path:
                    raise ValueError(
                        "packaged motion.render.frames"
                        f"[{index}].file must be {expected_path!r}"
                    )
        validate_render_pixel_budget(
            len(render_frames) * int(canvas[0]) * int(canvas[1])
        )
        total_duration = sum(int(frame["duration_ms"]) for frame in render_frames)
        authored_duration = sum(int(frame["duration_ms"]) for frame in frames)
        if total_duration != authored_duration:
            raise ValueError(
                "motion.render.frames must have the same total duration as motion.frames"
            )
        expected_count = total_duration * int(target_fps) / 1000
        if abs(len(render_frames) - expected_count) > 1:
            raise ValueError(
                "motion.render.target_fps is inconsistent with its frame count and duration"
            )

    return motion
