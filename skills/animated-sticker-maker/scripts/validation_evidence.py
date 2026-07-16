#!/usr/bin/env python3
"""Recompute objective validation evidence from current media artifacts."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from artifact_integrity import safe_relative_file, sha256_path
from gif_export_core import gif_safe_durations
from media_validation import (
    alpha_metrics,
    validate_gif,
    validate_sticker_webp,
    webp_alpha_guard_required,
)


DEFAULT_FRAME_RANGE = (4, 8)
DEFAULT_DURATION_RANGE_MS = (1200, 2000)


def inspect_png_frames(
    source_root: Path,
    entries: list[dict[str, object]],
    expected_size: tuple[int, int],
    label: str,
) -> tuple[list[str], list[dict[str, object]]]:
    source_modes: list[str] = []
    metrics: list[dict[str, object]] = []
    for index, entry in enumerate(entries):
        path = safe_relative_file(
            source_root,
            entry.get("file"),
            f"{label}[{index}].file",
        )
        with Image.open(path) as source:
            source.load()
            if source.format != "PNG":
                raise ValueError(f"{label}[{index}] must be a PNG file")
            source_modes.append(source.mode)
            rgba = source.convert("RGBA")
        metric = alpha_metrics(rgba)
        metrics.append(metric)
    return source_modes, metrics


def package_webp_alpha_guard_required(
    package: Path,
    motion: dict[str, object],
) -> bool:
    entries = motion["frames"]
    assert isinstance(entries, list)

    def rgba_frames():
        for index, entry in enumerate(entries):
            path = safe_relative_file(
                package / "source",
                entry.get("file"),
                f"frames[{index}].file",
            )
            with Image.open(path) as source:
                source.load()
                yield source.convert("RGBA")

    return webp_alpha_guard_required(rgba_frames())


def render_track_evidence(
    package: Path,
    motion: dict[str, object],
) -> tuple[dict[str, bool], list[dict[str, object]]]:
    render = motion.get("render")
    if not isinstance(render, dict):
        raise ValueError("packaged motion has no render track")
    entries = render["frames"]
    assert isinstance(entries, list)
    canvas = tuple(int(value) for value in motion["canvas"])
    source_modes, metrics = inspect_png_frames(
        package / "source",
        entries,
        canvas,
        "render.frames",
    )
    durations = [int(entry["duration_ms"]) for entry in entries]
    authored_total = sum(
        int(entry["duration_ms"]) for entry in motion["frames"]
    )
    checks = {
        "frame_count_matches_ordered_entries": len(metrics) == len(entries),
        "duration_count_matches_frames": len(durations) == len(metrics),
        "total_duration_matches_authored_keyframes": (
            sum(durations) == authored_total
        ),
        "target_fps_matches_timeline": abs(
            len(metrics)
            - sum(durations) * int(render["target_fps"]) / 1000
        )
        <= 1,
        "source_frames_are_rgba": all(
            mode == "RGBA" for mode in source_modes
        ),
        "all_frames_match_expected_size": all(
            tuple(metric["size"]) == canvas for metric in metrics
        ),
        "all_borders_transparent": all(
            metric["border_is_transparent"] is True for metric in metrics
        ),
        "all_frames_have_visible_pixels": all(
            metric["alpha_bbox"] is not None for metric in metrics
        ),
    }
    return checks, metrics


def package_source_evidence(
    package: Path,
    motion: dict[str, object],
    *,
    inspect_sticker: bool,
) -> tuple[
    dict[str, bool],
    list[dict[str, object]],
    dict[str, bool] | None,
    list[dict[str, object]] | None,
]:
    entries = motion["frames"]
    assert isinstance(entries, list)
    canvas = tuple(int(value) for value in motion["canvas"])
    source_modes, metrics = inspect_png_frames(
        package / "source",
        entries,
        canvas,
        "frames",
    )
    durations = [int(entry["duration_ms"]) for entry in entries]
    checks = {
        "frame_count_in_default_range": (
            DEFAULT_FRAME_RANGE[0] <= len(metrics) <= DEFAULT_FRAME_RANGE[1]
        ),
        "source_frames_are_rgba": all(
            mode == "RGBA" for mode in source_modes
        ),
        "all_frames_match_expected_size": all(
            tuple(metric["size"]) == canvas for metric in metrics
        ),
        "all_borders_transparent": all(
            metric["border_is_transparent"] is True for metric in metrics
        ),
        "all_frames_have_visible_pixels": all(
            metric["alpha_bbox"] is not None for metric in metrics
        ),
        "all_frames_are_unique": (
            len({metric["pixel_sha256"] for metric in metrics}) == len(metrics)
        ),
        "duration_in_default_range": (
            DEFAULT_DURATION_RANGE_MS[0]
            <= sum(durations)
            <= DEFAULT_DURATION_RANGE_MS[1]
        ),
    }
    render_checks = None
    render_metrics = None
    if isinstance(motion.get("render"), dict):
        render_checks, render_metrics = render_track_evidence(package, motion)
        checks["render_track_technical_validation_pass"] = all(
            render_checks.values()
        )
    if inspect_sticker:
        sticker = package / "sticker.webp"
        try:
            checks.update(
                validate_sticker_webp(
                    sticker,
                    canvas,
                    len(entries),
                    0 if motion["loop"] is True else 1,
                    durations,
                )
            )
        except (FileNotFoundError, OSError, ValueError):
            checks["sticker_is_readable"] = False
    return checks, metrics, render_checks, render_metrics


def expected_export_timeline(
    report: dict[str, object],
    motion: dict[str, object],
) -> tuple[
    list[dict[str, object]],
    list[int],
    int,
    list[int],
    bool,
]:
    if report.get("frame_track") == "render":
        render = motion.get("render")
        if not isinstance(render, dict):
            raise ValueError("render export has no declared render track")
        entries = render["frames"]
    else:
        entries = motion["frames"]
    assert isinstance(entries, list)
    source_durations = [int(entry["duration_ms"]) for entry in entries]
    total_duration = sum(source_durations)
    selected_fps = report["gif"]["selected_fps"]
    if selected_fps is None:
        expected_count = len(entries)
        expected_durations = source_durations
        allow_frame_collapse = False
    else:
        expected_count = max(
            2,
            round(total_duration * int(selected_fps) / 1000),
        )
        expected_durations = gif_safe_durations(
            total_duration,
            expected_count,
        )
        allow_frame_collapse = True
    return (
        entries,
        source_durations,
        expected_count,
        expected_durations,
        allow_frame_collapse,
    )


def validate_export_gif_evidence(
    gif_path: Path,
    report: dict[str, object],
    motion: dict[str, object],
) -> dict[str, object]:
    (
        entries,
        source_durations,
        expected_count,
        expected_durations,
        allow_frame_collapse,
    ) = expected_export_timeline(report, motion)
    expected_metadata = {
        "source_frame_count": len(entries),
        "source_total_duration_ms": sum(source_durations),
        "frame_count": expected_count,
        "total_duration_ms": sum(expected_durations),
    }
    for field, expected in expected_metadata.items():
        if report.get(field) != expected:
            raise ValueError(
                f"export report {field} does not match its source timeline"
            )
    canvas = report["canvas"]
    try:
        return validate_gif(
            gif_path,
            (int(canvas[0]), int(canvas[1])),
            expected_count,
            expected_durations,
            bool(motion["loop"]),
            allow_frame_collapse=allow_frame_collapse,
        )
    except (OSError, ValueError) as exc:
        raise ValueError(
            f"current GIF media failed validation: {exc}"
        ) from exc


def validate_preview_evidence(
    preview_path: Path,
    preview: dict[str, object],
    canvas: tuple[int, int],
) -> None:
    try:
        with Image.open(preview_path) as image:
            image.load()
            image_format = image.format
            image_mode = image.mode
            image_size = image.size
            metrics = alpha_metrics(image.convert("RGBA"))
    except OSError as exc:
        raise ValueError(
            f"current preview media is unreadable: {exc}"
        ) from exc
    if image_format != "PNG":
        raise ValueError("exported preview must be PNG")
    if image_size != canvas:
        raise ValueError("exported preview size does not match the report canvas")
    expected_mode = "indexed" if image_mode == "P" else "rgba"
    if preview.get("mode") != expected_mode:
        raise ValueError("export report preview.mode does not match its file")
    if metrics["alpha_bbox"] is None:
        raise ValueError("exported preview must contain visible pixels")
    if metrics["border_is_transparent"] is not True:
        raise ValueError("exported preview border must be transparent")
    if preview.get("sha256") != sha256_path(preview_path):
        raise ValueError("export report preview.sha256 does not match its file")
