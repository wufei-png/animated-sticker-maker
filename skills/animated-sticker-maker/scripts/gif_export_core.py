#!/usr/bin/env python3
"""Deterministic frame fitting, GIF timing, palette, and preview operations."""

from __future__ import annotations

import bisect
from pathlib import Path

import numpy as np
from PIL import Image


COLOR_CANDIDATES = (255, 224, 192, 160, 128, 96, 64, 48, 32)
MAX_PALETTE_SAMPLES = 500_000
TRANSPARENT_INDEX = 255
RESAMPLING_FILTERS = {
    "lanczos": Image.Resampling.LANCZOS,
    "nearest": Image.Resampling.NEAREST,
}


def fit_frame(
    frame: Image.Image,
    size: tuple[int, int],
    resampling: str = "lanczos",
) -> Image.Image:
    if resampling not in RESAMPLING_FILTERS:
        raise ValueError("resampling must be 'lanczos' or 'nearest'")
    scale = min(size[0] / frame.width, size[1] / frame.height)
    if resampling == "nearest" and scale >= 1:
        scale = max(1, int(scale))
    fitted_size = (
        max(1, round(frame.width * scale)),
        max(1, round(frame.height * scale)),
    )
    fitted = frame.resize(fitted_size, RESAMPLING_FILTERS[resampling])
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.alpha_composite(
        fitted,
        ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2),
    )
    return canvas


def collect_palette_samples(
    frames: list[Image.Image],
    alpha_threshold: int,
    max_samples: int = MAX_PALETTE_SAMPLES,
) -> np.ndarray:
    if max_samples <= 0:
        raise ValueError("max_samples must be positive")
    samples: list[np.ndarray] = []
    frame_count = len(frames)
    base_budget, extra_budget = divmod(max_samples, max(1, frame_count))
    for index, frame in enumerate(frames):
        budget = base_budget + (1 if index < extra_budget else 0)
        if budget == 0:
            continue
        rgba = np.asarray(frame)
        visible = rgba[..., :3][rgba[..., 3] >= alpha_threshold]
        if visible.size:
            if len(visible) > budget:
                step = max(1, (len(visible) + budget - 1) // budget)
                visible = visible[::step][:budget]
            samples.append(visible)
    if not samples:
        raise ValueError(
            "frames contain no visible pixels at the selected alpha threshold"
        )
    rgb = np.concatenate(samples, axis=0)
    if len(rgb) > max_samples:
        raise AssertionError("palette sample budget exceeded")
    return rgb


def make_global_palette(
    frames: list[Image.Image], colors: int, alpha_threshold: int
) -> Image.Image:
    rgb = collect_palette_samples(frames, alpha_threshold)
    sample_image = Image.fromarray(rgb.reshape(1, len(rgb), 3), mode="RGB")
    palette = sample_image.quantize(
        colors=colors,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )
    palette_data = palette.getpalette()
    palette_data[TRANSPARENT_INDEX * 3 : TRANSPARENT_INDEX * 3 + 3] = [0, 0, 0]
    palette.putpalette(palette_data)
    return palette


def quantize_frames(
    frames: list[Image.Image], colors: int, alpha_threshold: int
) -> list[Image.Image]:
    palette = make_global_palette(frames, colors, alpha_threshold)
    palette_data = palette.getpalette()
    result: list[Image.Image] = []
    for frame in frames:
        indexed = frame.convert("RGB").quantize(
            palette=palette,
            dither=Image.Dither.FLOYDSTEINBERG,
        )
        indices = np.asarray(indexed).copy()
        indices[np.asarray(frame.getchannel("A")) < alpha_threshold] = (
            TRANSPARENT_INDEX
        )
        indexed = Image.fromarray(indices, mode="P")
        indexed.putpalette(palette_data)
        indexed.info["transparency"] = TRANSPARENT_INDEX
        result.append(indexed)
    return result


def write_gif(
    frames: list[Image.Image],
    durations: list[int],
    path: Path,
    colors: int,
    alpha_threshold: int,
    loop: bool,
) -> None:
    indexed = quantize_frames(frames, colors, alpha_threshold)
    save_options = {
        "format": "GIF",
        "save_all": True,
        "append_images": indexed[1:],
        "duration": durations,
        "disposal": 2,
        "transparency": TRANSPARENT_INDEX,
        "optimize": True,
    }
    if loop:
        save_options["loop"] = 0
    indexed[0].save(path, **save_options)


def gif_safe_durations(total_ms: int, frame_count: int) -> list[int]:
    if frame_count <= 0:
        raise ValueError("frame count must be positive")
    rounded_total = max(10, round(total_ms / 10) * 10)
    boundaries = [
        round((index * rounded_total / frame_count) / 10) * 10
        for index in range(frame_count + 1)
    ]
    durations = [end - start for start, end in zip(boundaries, boundaries[1:])]
    if any(duration <= 0 for duration in durations):
        raise ValueError("requested fps is too high for GIF's 10 ms timing precision")
    return durations


def resample_timeline(
    frames: list[Image.Image], durations: list[int], fps: int
) -> tuple[list[Image.Image], list[int]]:
    if len(frames) != len(durations) or not frames:
        raise ValueError("frames and durations must have equal non-zero length")
    if fps <= 0 or fps > 100:
        raise ValueError("fps must be between 1 and 100")
    total_ms = sum(durations)
    target_count = max(2, round(total_ms * fps / 1000))
    source_ends: list[int] = []
    elapsed = 0
    for duration in durations:
        elapsed += duration
        source_ends.append(elapsed)
    samples: list[Image.Image] = []
    for index in range(target_count):
        timestamp = index * total_ms / target_count
        source_index = min(
            len(frames) - 1,
            bisect.bisect_right(source_ends, timestamp),
        )
        samples.append(frames[source_index])
    return samples, gif_safe_durations(total_ms, target_count)


def try_export_gif(
    frames: list[Image.Image],
    durations: list[int],
    output: Path,
    max_bytes: int | None,
    alpha_threshold: int,
    loop: bool,
    color_candidates: tuple[int, ...],
    nominal_fps: int | None,
) -> tuple[tuple[int, int] | None, list[dict[str, int | None]]]:
    candidate = output.with_suffix(output.suffix + ".candidate")
    attempts: list[dict[str, int | None]] = []
    try:
        for colors in color_candidates:
            write_gif(
                frames,
                durations,
                candidate,
                colors,
                alpha_threshold,
                loop,
            )
            byte_size = candidate.stat().st_size
            attempts.append(
                {"fps": nominal_fps, "colors": colors, "bytes": byte_size}
            )
            if max_bytes is None or byte_size <= max_bytes:
                candidate.replace(output)
                return (colors, byte_size), attempts
    finally:
        candidate.unlink(missing_ok=True)
    return None, attempts


def export_gif(
    frames: list[Image.Image],
    durations: list[int],
    output: Path,
    max_bytes: int | None,
    alpha_threshold: int,
    loop: bool,
    min_colors: int = 32,
    fps_candidates: tuple[int, ...] | None = None,
) -> tuple[
    list[Image.Image],
    list[int],
    int,
    int,
    int | None,
    list[dict[str, int | None]],
]:
    color_candidates = tuple(
        colors for colors in COLOR_CANDIDATES if colors >= min_colors
    )
    if not color_candidates:
        raise ValueError(
            f"minimum color count {min_colors} excludes every supported palette candidate"
        )
    variants: list[tuple[int | None, list[Image.Image], list[int]]]
    if fps_candidates:
        variants = [
            (fps, *resample_timeline(frames, durations, fps))
            for fps in fps_candidates
        ]
    else:
        variants = [(None, frames, durations)]

    all_attempts: list[dict[str, int | None]] = []
    for nominal_fps, variant_frames, variant_durations in variants:
        selected, attempts = try_export_gif(
            variant_frames,
            variant_durations,
            output,
            max_bytes,
            alpha_threshold,
            loop,
            color_candidates,
            nominal_fps,
        )
        all_attempts.extend(attempts)
        if selected is not None:
            colors, byte_size = selected
            return (
                variant_frames,
                variant_durations,
                colors,
                byte_size,
                nominal_fps,
                all_attempts,
            )

    smallest = min(all_attempts, key=lambda item: int(item["bytes"] or 0))
    raise ValueError(
        f"GIF cannot meet {max_bytes} bytes with the requested quality floor; "
        f"smallest candidate is {smallest['bytes']} bytes at "
        f"fps={smallest['fps']} and {smallest['colors']} colors"
    )


def write_preview(
    frame: Image.Image, output: Path, max_bytes: int | None
) -> tuple[str, int, int | None]:
    frame.save(output, format="PNG", optimize=True, compress_level=9)
    byte_size = output.stat().st_size
    if max_bytes is None or byte_size <= max_bytes:
        return "rgba", byte_size, None

    smallest: tuple[int, int] | None = None
    candidate = output.with_suffix(output.suffix + ".candidate")
    try:
        for colors in (256, 192, 128, 96, 64, 48, 32, 24, 16):
            indexed = frame.quantize(
                colors=colors,
                method=Image.Quantize.FASTOCTREE,
                dither=Image.Dither.FLOYDSTEINBERG,
            )
            indexed.save(candidate, format="PNG", optimize=True, compress_level=9)
            candidate_size = candidate.stat().st_size
            if smallest is None or candidate_size < smallest[1]:
                smallest = (colors, candidate_size)
            if candidate_size <= max_bytes:
                candidate.replace(output)
                return "indexed", candidate_size, colors
    finally:
        candidate.unlink(missing_ok=True)
    output.unlink(missing_ok=True)
    assert smallest is not None
    raise ValueError(
        f"preview PNG cannot meet {max_bytes} bytes at the requested size; "
        f"smallest candidate is {smallest[1]} bytes at {smallest[0]} colors"
    )
