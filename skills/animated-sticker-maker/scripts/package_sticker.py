#!/usr/bin/env python3
"""Validate RGBA frames and build the default animated-sticker package."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import shutil
import struct
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from artifact_integrity import (
    package_fingerprint,
    render_track_fingerprint,
    sha256_path,
)
from motion_schema import validate_motion, validate_render_pixel_budget


DEFAULT_SIZE = (1024, 1024)
DEFAULT_FRAME_RANGE = (4, 8)
DEFAULT_DURATION_RANGE_MS = (1200, 2000)
RESAMPLING_FILTERS = {
    "lanczos": Image.Resampling.LANCZOS,
    "nearest": Image.Resampling.NEAREST,
}


def parse_size(value: str) -> tuple[int, int]:
    parts = value.lower().split("x", 1)
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("expected size must look like 1024x1024")
    try:
        width, height = (int(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected size must look like 1024x1024") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("expected size must be positive")
    return width, height


def load_motion(path: Path) -> dict[str, object]:
    motion = json.loads(path.read_text(encoding="utf-8"))
    return validate_motion(motion, packaged=False)


def resolve_frame(frames_dir: Path, file_value: str) -> Path:
    relative = Path(file_value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("motion frame paths must stay beneath the frames directory")
    candidates = [frames_dir / relative, frames_dir / relative.name]
    for candidate in candidates:
        if (
            candidate.is_file()
            and candidate.resolve().is_relative_to(frames_dir.resolve())
        ):
            return candidate
    raise FileNotFoundError(f"frame not found for {file_value!r} in {frames_dir}")


def resolve_render_frames(
    motion_path: Path, frame_entries: list[dict[str, object]]
) -> list[Path]:
    root = motion_path.parent.resolve()
    frames: list[Path] = []
    for index, entry in enumerate(frame_entries):
        relative = Path(str(entry["file"]))
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"render frame not found: {path}")
        if not path.resolve().is_relative_to(root):
            raise ValueError(
                f"motion.render.frames[{index}].file must not escape through a symbolic link"
            )
        frames.append(path)
    return frames


def reference_metadata(reference_image: Path, source_dir: Path, include: bool) -> dict[str, object]:
    if not reference_image.is_file():
        raise FileNotFoundError(f"reference image not found: {reference_image}")
    with Image.open(reference_image) as image:
        image.load()
        metadata: dict[str, object] = {
            "filename": reference_image.name,
            "sha256": sha256_path(reference_image),
            "bytes": reference_image.stat().st_size,
            "format": image.format,
            "mode": image.mode,
            "dimensions": list(image.size),
            "included_path": None,
        }
    if include:
        destination = source_dir / "reference" / reference_image.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(reference_image, destination)
        metadata["included_path"] = f"reference/{reference_image.name}"
    (source_dir / "reference.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


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


def checkerboard(size: tuple[int, int], cell: int = 16) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, (238, 242, 242))
    draw = ImageDraw.Draw(image)
    for y in range(0, height, cell):
        for x in range(0, width, cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(211, 220, 220))
    return image


def label_font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def make_contact_sheet(
    frames: list[Image.Image],
    durations: list[int],
    path: Path,
    resampling: str,
) -> None:
    columns = min(4, math.ceil(math.sqrt(len(frames))))
    rows = math.ceil(len(frames) / columns)
    tile = 320
    label_height = 38
    sheet = Image.new("RGB", (columns * tile, rows * (tile + label_height)), "white")
    font = label_font(18)
    for index, frame in enumerate(frames):
        x = (index % columns) * tile
        y = (index // columns) * (tile + label_height)
        background = checkerboard((tile, tile))
        if resampling == "nearest" and frame.width <= tile and frame.height <= tile:
            integer_scale = max(1, min(tile // frame.width, tile // frame.height))
            preview_size = (
                frame.width * integer_scale,
                frame.height * integer_scale,
            )
        else:
            scale = min(tile / frame.width, tile / frame.height)
            preview_size = (
                max(1, round(frame.width * scale)),
                max(1, round(frame.height * scale)),
            )
        preview = frame.resize(preview_size, RESAMPLING_FILTERS[resampling])
        px = (tile - preview.width) // 2
        py = (tile - preview.height) // 2
        background.paste(preview, (px, py), preview.getchannel("A"))
        sheet.paste(background, (x, y))
        ImageDraw.Draw(sheet).text(
            (x + 10, y + tile + 8),
            f"F{index + 1}  {durations[index]} ms",
            font=font,
            fill=(20, 55, 53),
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


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


def prepare_webp_frames(frames: list[Image.Image]) -> tuple[list[Image.Image], bool]:
    """Ensure libwebp marks a cropped animation as alpha-bearing.

    When every frame's non-transparent bounding box is a solid rectangle,
    libwebp may omit the global alpha flag and decode the transparent canvas as
    opaque. Making one already-visible pixel nearly opaque forces the flag while
    remaining visually indistinguishable.
    """
    for frame in frames:
        alpha = np.asarray(frame.getchannel("A"))
        visible = np.where(alpha > 0)
        if not visible[0].size:
            continue
        left, right = int(visible[1].min()), int(visible[1].max() + 1)
        top, bottom = int(visible[0].min()), int(visible[0].max() + 1)
        if np.any(alpha[top:bottom, left:right] < 255):
            return frames, False

    guarded = [frame.copy() for frame in frames]
    alpha = np.asarray(guarded[0].getchannel("A"))
    visible = np.argwhere(alpha > 0)
    if not visible.size:
        return guarded, False
    y, x = (int(value) for value in visible[0])
    red, green, blue, _ = guarded[0].getpixel((x, y))
    guarded[0].putpixel((x, y), (red, green, blue, 254))
    return guarded, True


def initialize_output(output: Path) -> tuple[Path, Path]:
    """Create the empty output tree inside the transaction's staging directory."""
    source = output / "source"
    validation = output / "validation"
    frame_output = source / "frames"
    frame_output.mkdir(parents=True, exist_ok=True)
    validation.mkdir(parents=True, exist_ok=True)
    return frame_output, validation


def build_candidate(args: argparse.Namespace) -> int:
    motion = load_motion(args.motion)
    canvas = motion["canvas"]
    if tuple(canvas) != args.expected_size:
        raise ValueError(
            f"motion.canvas {canvas} does not match --expected-size {args.expected_size}"
        )
    frame_entries = motion["frames"]
    frame_paths = [resolve_frame(args.frames_dir, entry["file"]) for entry in frame_entries]
    semantic_hold_index = None
    semantic_hold = motion.get("semantic_hold_frame")
    if semantic_hold is not None:
        if not isinstance(semantic_hold, str) or not semantic_hold:
            raise ValueError("semantic_hold_frame must be a non-empty frame path")
        semantic_hold_path = resolve_frame(args.frames_dir, semantic_hold).resolve()
        matching_indices = [
            index
            for index, frame_path in enumerate(frame_paths)
            if frame_path.resolve() == semantic_hold_path
        ]
        if len(matching_indices) != 1:
            raise ValueError(
                "semantic_hold_frame must name exactly one authored motion frame"
            )
        semantic_hold_index = matching_indices[0]
    frames: list[Image.Image] = []
    source_modes: list[str] = []
    for path in frame_paths:
        with Image.open(path) as source:
            source_modes.append(source.mode)
            frames.append(source.convert("RGBA"))
    durations = [entry["duration_ms"] for entry in frame_entries]
    total_duration = sum(durations)
    metrics = [alpha_metrics(frame) for frame in frames]

    checks = {
        "frame_count_in_default_range": args.allow_nonstandard_frame_count
        or DEFAULT_FRAME_RANGE[0] <= len(frames) <= DEFAULT_FRAME_RANGE[1],
        "source_frames_are_rgba": all(mode == "RGBA" for mode in source_modes),
        "all_frames_match_expected_size": all(frame.size == args.expected_size for frame in frames),
        "all_borders_transparent": all(metric["border_is_transparent"] for metric in metrics),
        "all_frames_have_visible_pixels": all(metric["alpha_bbox"] is not None for metric in metrics),
        "all_frames_are_unique": len({metric["pixel_sha256"] for metric in metrics}) == len(frames),
        "duration_in_default_range": args.allow_nonstandard_timing
        or DEFAULT_DURATION_RANGE_MS[0] <= total_duration <= DEFAULT_DURATION_RANGE_MS[1],
    }
    technical_pass = all(checks.values())

    frame_output, validation_dir = initialize_output(args.output)
    source_dir = args.output / "source"
    reference = reference_metadata(
        args.reference_image,
        source_dir,
        args.include_reference,
    )
    packaged_motion = copy.deepcopy(motion)
    packaged_motion.pop("reference_image", None)
    packaged_motion["reference"] = {
        "filename": reference["filename"],
        "sha256": reference["sha256"],
        "included_path": reference["included_path"],
    }
    for index, (frame, entry) in enumerate(zip(frames, packaged_motion["frames"])):
        normalized_name = f"{index:03d}.png"
        frame.save(frame_output / normalized_name, format="PNG")
        canonical_name = f"frames/{normalized_name}"
        entry["file"] = canonical_name
    if semantic_hold_index is not None:
        packaged_motion["semantic_hold_frame"] = (
            packaged_motion["frames"][semantic_hold_index]["file"]
        )
    render_summary = None
    render_report = None
    render = motion.get("render")
    if isinstance(render, dict):
        render_entries = render["frames"]
        assert isinstance(render_entries, list)
        render_paths = resolve_render_frames(args.motion, render_entries)
        render_frames: list[Image.Image] = []
        render_source_modes: list[str] = []
        render_input_pixels = 0
        for path in render_paths:
            with Image.open(path) as source:
                render_input_pixels += source.width * source.height
                validate_render_pixel_budget(render_input_pixels)
                render_source_modes.append(source.mode)
                render_frames.append(source.convert("RGBA"))
        render_durations = [int(entry["duration_ms"]) for entry in render_entries]
        render_metrics = [alpha_metrics(frame) for frame in render_frames]
        render_checks = {
            "frame_count_matches_ordered_entries": len(render_frames)
            == len(render_entries),
            "duration_count_matches_frames": len(render_durations) == len(render_frames),
            "total_duration_matches_authored_keyframes": sum(render_durations)
            == total_duration,
            "target_fps_matches_timeline": abs(
                len(render_frames)
                - sum(render_durations) * int(render["target_fps"]) / 1000
            )
            <= 1,
            "source_frames_are_rgba": all(mode == "RGBA" for mode in render_source_modes),
            "all_frames_match_expected_size": all(
                frame.size == args.expected_size for frame in render_frames
            ),
            "all_borders_transparent": all(
                metric["border_is_transparent"] for metric in render_metrics
            ),
            "all_frames_have_visible_pixels": all(
                metric["alpha_bbox"] is not None for metric in render_metrics
            ),
        }
        render_pass = all(render_checks.values())
        checks["render_track_technical_validation_pass"] = render_pass
        technical_pass = technical_pass and render_pass
        render_output = source_dir / "rendered-frames"
        render_output.mkdir(parents=True, exist_ok=True)
        for index, frame in enumerate(render_frames):
            frame.save(render_output / f"{index:04d}.png", format="PNG")
        packaged_render: dict[str, object] = {
            "target_fps": render["target_fps"],
            "frames": [],
        }
        packaged_render_frames = packaged_render["frames"]
        assert isinstance(packaged_render_frames, list)
        for index, entry in enumerate(render_entries):
            packaged_entry = copy.deepcopy(entry)
            packaged_entry["file"] = f"rendered-frames/{index:04d}.png"
            packaged_render_frames.append(packaged_entry)
        packaged_motion["render"] = packaged_render
        make_contact_sheet(
            render_frames,
            render_durations,
            validation_dir / "render-contact-sheet.png",
            str(packaged_motion["resampling"]),
        )
        render_summary = {
            "target_fps": render["target_fps"],
            "frame_count": len(render_frames),
            "total_duration_ms": sum(render_durations),
        }
        render_report = {
            "status": (
                "pending_visual_validation"
                if render_pass
                else "technical_validation_failed"
            ),
            "deliverable_ready": False,
            "artifact_scope": "render_track",
            "technical_validation": {
                "status": "pass" if render_pass else "fail",
                "checks": render_checks,
            },
            "visual_validation": {
                "status": "pending",
                "required": ["identity", "meaning", "loop", "alpha", "small_size"],
                "notes": {},
            },
            **render_summary,
            "frames": render_metrics,
        }

    (source_dir / "motion.json").write_text(
        json.dumps(packaged_motion, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if render_report is not None:
        render_report["artifact_fingerprint"] = render_track_fingerprint(args.output)
        (validation_dir / "render-report.json").write_text(
            json.dumps(render_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    resampling = str(packaged_motion["resampling"])
    make_contact_sheet(
        frames,
        durations,
        validation_dir / "contact-sheet.png",
        resampling,
    )

    loop_count = 0 if bool(motion.get("loop", True)) else 1
    sticker_path = args.output / "sticker.webp"
    output_validation_error = None
    alpha_guard_applied = False
    if technical_pass:
        encoded_frames, alpha_guard_applied = prepare_webp_frames(frames)
        lossless = resampling == "nearest"
        try:
            encoded_frames[0].save(
                sticker_path,
                save_all=True,
                append_images=encoded_frames[1:],
                duration=durations,
                loop=loop_count,
                lossless=lossless,
                quality=args.quality,
                method=6,
                minimize_size=True,
                allow_mixed=not lossless,
            )
            checks.update(
                validate_sticker_webp(
                    sticker_path,
                    args.expected_size,
                    len(frames),
                    loop_count,
                    durations,
                )
            )
        except (OSError, ValueError) as exc:
            checks["sticker_is_readable"] = False
            output_validation_error = str(exc)
        technical_pass = all(checks.values())

    report = {
        "status": (
            "pending_visual_validation"
            if technical_pass
            else "technical_validation_failed"
        ),
        "deliverable_ready": False,
        "artifact_scope": "package_source",
        "artifact_fingerprint": package_fingerprint(args.output),
        "technical_validation": {
            "status": "pass" if technical_pass else "fail",
            "checks": checks,
        },
        "visual_validation": {
            "status": "pending",
            "required": ["identity", "meaning", "loop", "alpha", "small_size"],
            "notes": {},
        },
        "canvas": list(args.expected_size),
        "frame_count": len(frames),
        "total_duration_ms": total_duration,
        "resampling": resampling,
        "webp_encoding": {
            "lossless": resampling == "nearest",
            "alpha_guard_applied": alpha_guard_applied,
        },
        "reference": reference,
        "render_track": render_summary,
        "frames": metrics,
    }
    if output_validation_error is not None:
        report["output_validation_error"] = output_validation_error
    (validation_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    if not technical_pass:
        return 2
    return 0


def package(args: argparse.Namespace) -> int:
    final_output = args.output.resolve()
    final_output.parent.mkdir(parents=True, exist_ok=True)
    failed_output = final_output.with_name(f"{final_output.name}.failed")
    with tempfile.TemporaryDirectory(
        prefix=f".{final_output.name}.staging-",
        dir=final_output.parent,
    ) as temporary:
        staged_output = Path(temporary) / final_output.name
        staged_args = copy.copy(args)
        staged_args.output = staged_output
        result = build_candidate(staged_args)
        if result != 0:
            if failed_output.exists():
                shutil.rmtree(failed_output)
            staged_output.replace(failed_output)
            print(
                "Technical validation failed; existing package preserved. Inspect "
                f"{failed_output / 'validation' / 'report.json'}"
            )
            return result

        previous_output = Path(temporary) / "previous-package"
        if final_output.exists():
            final_output.replace(previous_output)
        try:
            staged_output.replace(final_output)
        except Exception:
            if previous_output.exists() and not final_output.exists():
                previous_output.replace(final_output)
            raise
        if failed_output.exists():
            shutil.rmtree(failed_output)

    print(f"Wrote {final_output / 'sticker.webp'}")
    print(
        "Technical validation passed; visual validation remains: "
        f"{final_output / 'validation' / 'report.json'}"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames-dir", type=Path, required=True)
    parser.add_argument("--motion", type=Path, required=True)
    parser.add_argument("--reference-image", type=Path, required=True)
    parser.add_argument(
        "--include-reference",
        action="store_true",
        help="include an exact copy of the reference image in source/reference/",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-size", type=parse_size, default=DEFAULT_SIZE)
    parser.add_argument("--quality", type=int, default=92, choices=range(1, 101))
    parser.add_argument("--allow-nonstandard-frame-count", action="store_true")
    parser.add_argument("--allow-nonstandard-timing", action="store_true")
    args = parser.parse_args()
    raise SystemExit(package(args))


if __name__ == "__main__":
    main()
