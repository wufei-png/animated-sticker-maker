#!/usr/bin/env python3
"""Resolve and decode media used by the offline Review Page model."""

from __future__ import annotations

import base64
import os
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from PIL import Image

from artifact_integrity import safe_relative_file
from media_validation import webp_animation_durations


def relative_media_url(path: Path, output_dir: Path) -> str:
    relative = Path(
        os.path.relpath(path.resolve(), start=output_dir.resolve())
    ).as_posix()
    return quote(relative, safe="/")


def image_data_uri(path: Path) -> str:
    with Image.open(path) as image:
        image.load()
        image_format = image.format
    mime = Image.MIME.get(str(image_format), "application/octet-stream")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def png_data_uri(image: Image.Image) -> str:
    buffer = BytesIO()
    image.convert("RGBA").save(buffer, format="PNG", optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def frame_records(
    entries: object,
    source: Path,
    output_dir: Path,
    *,
    prefix: str,
) -> list[dict[str, object]]:
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{prefix} frames must be a non-empty array")
    records: list[dict[str, object]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"{prefix} frames[{index}] must be an object")
        path = safe_relative_file(
            source,
            entry.get("file"),
            f"{prefix}.frames[{index}].file",
        )
        records.append(
            {
                "index": index,
                "label": (
                    f"F{index + 1}"
                    if prefix == "authored"
                    else f"R{index + 1:04d}"
                ),
                "src": relative_media_url(path, output_dir),
                "path": str(entry["file"]),
                "duration_ms": int(entry["duration_ms"]),
                "description": entry.get("description"),
            }
        )
    return records


def encoded_frame_records(
    path: Path,
    package: Path,
    *,
    format_label: str,
    description_template: str,
) -> list[dict[str, object]]:
    with Image.open(path) as image:
        frame_count = getattr(image, "n_frames", 1)
        if frame_count < 1:
            raise ValueError(f"encoded artifact has no frames: {path}")
        if image.format == "WEBP":
            durations = webp_animation_durations(path)
        else:
            durations = []
            for index in range(frame_count):
                image.seek(index)
                duration = image.info.get("duration")
                durations.append(duration if isinstance(duration, int) else 0)
        if len(durations) != frame_count or any(
            not isinstance(duration, int) or duration <= 0
            for duration in durations
        ):
            raise ValueError(
                f"encoded artifact has invalid frame timing: {path}"
            )

        try:
            display_path = path.resolve().relative_to(
                package.resolve()
            ).as_posix()
        except ValueError:
            display_path = path.name
        records: list[dict[str, object]] = []
        for index, duration in enumerate(durations):
            image.seek(index)
            records.append(
                {
                    "index": index,
                    "label": f"E{index + 1:04d}",
                    "src": png_data_uri(image.convert("RGBA")),
                    "path": f"{display_path}#frame={index + 1}",
                    "duration_ms": duration,
                    "description": description_template.format(
                        format_label=format_label
                    ),
                }
            )
    return records
