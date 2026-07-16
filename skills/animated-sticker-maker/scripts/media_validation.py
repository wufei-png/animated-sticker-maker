#!/usr/bin/env python3
"""Shared deterministic media inspection for packages, exports, and doctor."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import numpy as np
from PIL import Image


def alpha_metrics(image: Image.Image) -> dict[str, object]:
    alpha = np.asarray(image.getchannel("A"))
    visible = np.where(alpha > 16)
    bbox = None
    if visible[0].size:
        bbox = [
            int(visible[1].min()),
            int(visible[0].min()),
            int(visible[1].max() + 1),
            int(visible[0].max() + 1),
        ]
    border_is_transparent = bool(
        np.all(alpha[0] == 0)
        and np.all(alpha[-1] == 0)
        and np.all(alpha[:, 0] == 0)
        and np.all(alpha[:, -1] == 0)
    )
    return {
        "size": list(image.size),
        "mode": image.mode,
        "alpha_bbox": bbox,
        "transparent_pixels": int(np.count_nonzero(alpha == 0)),
        "partial_alpha_pixels": int(np.count_nonzero((alpha > 0) & (alpha < 255))),
        "border_is_transparent": border_is_transparent,
        "pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
    }


def webp_animation_durations(path: Path) -> list[int]:
    """Read ANMF durations directly from an animated WebP RIFF container."""
    data = path.read_bytes()
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("encoded sticker is not a valid WebP RIFF container")
    riff_size = struct.unpack_from("<I", data, 4)[0]
    container_end = riff_size + 8
    if container_end > len(data):
        raise ValueError("encoded WebP RIFF container is truncated")
    durations: list[int] = []
    offset = 12
    while offset + 8 <= container_end:
        chunk_type = data[offset : offset + 4]
        chunk_size = struct.unpack_from("<I", data, offset + 4)[0]
        payload_start = offset + 8
        payload_end = payload_start + chunk_size
        if payload_end > container_end:
            raise ValueError("encoded WebP contains a truncated chunk")
        if chunk_type == b"ANMF":
            if chunk_size < 16:
                raise ValueError("encoded WebP contains a malformed ANMF chunk")
            durations.append(
                int.from_bytes(data[payload_start + 12 : payload_start + 15], "little")
            )
        offset = payload_end + (chunk_size % 2)
    return durations


def validate_sticker_webp(
    path: Path,
    expected_size: tuple[int, int],
    expected_frame_count: int,
    expected_loop_count: int,
    expected_durations: list[int],
) -> dict[str, bool]:
    """Re-open the encoded deliverable and verify its observable structure."""
    with Image.open(path) as image:
        frame_count = getattr(image, "n_frames", 1)
        checks = {
            "sticker_is_webp": image.format == "WEBP",
            "sticker_matches_expected_size": image.size == expected_size,
            "sticker_frame_count_matches_source": frame_count == expected_frame_count,
            "sticker_loop_matches_motion": image.info.get("loop") == expected_loop_count,
        }
        transparency_preserved = True
        for index in range(frame_count):
            image.seek(index)
            alpha = np.asarray(image.convert("RGBA").getchannel("A"))
            transparency_preserved = transparency_preserved and bool(
                np.any(alpha == 0) and np.any(alpha > 0)
            )
        checks["sticker_transparency_preserved"] = transparency_preserved
    checks["sticker_durations_match_source"] = (
        webp_animation_durations(path) == expected_durations
    )
    return checks


def validate_gif(
    path: Path,
    size: tuple[int, int],
    frame_count: int,
    durations: list[int],
    loop: bool,
    allow_frame_collapse: bool = False,
) -> dict[str, object]:
    expected_loop = 0 if loop else None
    actual_durations: list[int | None] = []
    transparent_borders: list[bool] = []
    with Image.open(path) as image:
        encoded_format = image.format
        encoded_frame_count = getattr(image, "n_frames", 1)
        encoded_size = image.size
        for index in range(encoded_frame_count):
            image.seek(index)
            actual_durations.append(image.info.get("duration"))
            alpha = np.asarray(image.convert("RGBA").getchannel("A"))
            transparent_borders.append(
                bool(
                    np.all(alpha[0] == 0)
                    and np.all(alpha[-1] == 0)
                    and np.all(alpha[:, 0] == 0)
                    and np.all(alpha[:, -1] == 0)
                )
            )
        encoded_loop = image.info.get("loop")
    actual_duration_values = [
        value for value in actual_durations if isinstance(value, int)
    ]
    frame_count_matches = encoded_frame_count == frame_count
    if allow_frame_collapse:
        frame_count_matches = 1 < encoded_frame_count <= frame_count
    durations_preserved = len(actual_durations) == len(durations) and all(
        isinstance(actual, int) and abs(actual - expected) <= 10
        for actual, expected in zip(actual_durations, durations)
    )
    if allow_frame_collapse:
        durations_preserved = (
            len(actual_duration_values) == len(actual_durations)
            and abs(sum(actual_duration_values) - sum(durations)) <= 10
        )
    checks = {
        "gif_is_gif": encoded_format == "GIF",
        "size_matches": encoded_size == size,
        "frame_count_matches": frame_count_matches,
        "durations_preserved": durations_preserved,
        "loop_matches": encoded_loop == expected_loop,
        "all_borders_transparent": all(transparent_borders),
    }
    if not all(checks.values()):
        raise ValueError(f"exported GIF validation failed: {checks}")
    return {
        "checks": checks,
        "encoded_frame_count": encoded_frame_count,
        "durations_ms": actual_durations,
        "total_duration_ms": sum(actual_duration_values),
    }
