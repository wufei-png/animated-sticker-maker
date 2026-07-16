#!/usr/bin/env python3
"""Export a validated sticker package as a constrained GIF and preview PNG."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from artifact_integrity import (
    fingerprint_files,
    sha256_path,
)
from export_package import automatic_preview_frame, load_validated_package
from export_transaction import (
    commit_staged_files,
    direct_export_path,
    prepare_export_directory,
    previous_export_artifacts,
)
from gif_export_core import (
    RESAMPLING_FILTERS,
    collect_palette_samples,
    export_gif,
    fit_frame,
    gif_safe_durations,
    resample_timeline,
    write_gif,
    write_preview,
)
from media_validation import validate_gif
from validation_integrity import (
    REPORT_SCHEMA_VERSION,
    validate_report_state,
)
from validation_schema import validate_report_contract


PLATFORM_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def parse_size(value: str) -> tuple[int, int]:
    parts = value.lower().split("x", 1)
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("size must look like 400x400")
    try:
        width, height = (int(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("size must look like 400x400") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("size must be positive")
    return width, height


def parse_fps_candidates(value: str) -> tuple[int, ...]:
    try:
        candidates = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "fps candidates must be comma-separated positive integers"
        ) from exc
    if not candidates or any(value <= 0 or value > 100 for value in candidates):
        raise argparse.ArgumentTypeError(
            "fps candidates must be comma-separated integers from 1 to 100"
        )
    if len(set(candidates)) != len(candidates):
        raise argparse.ArgumentTypeError("fps candidates must not contain duplicates")
    if any(left <= right for left, right in zip(candidates, candidates[1:])):
        raise argparse.ArgumentTypeError(
            "fps candidates must be ordered from highest to lowest"
        )
    return candidates


def parse_spec_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise argparse.ArgumentTypeError(
            "spec URL must be an absolute http(s) URL to the verified platform specification"
        )
    return value


def parse_platform(value: str) -> str:
    if not PLATFORM_PATTERN.fullmatch(value) or value in {".", ".."}:
        raise argparse.ArgumentTypeError(
            "platform must be one safe path segment using letters, digits, dot, dash, or underscore"
        )
    return value


def parse_verified_on(value: str) -> str:
    try:
        verified = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "verified-on must be an ISO date in YYYY-MM-DD form"
        ) from exc
    if verified > date.today():
        raise argparse.ArgumentTypeError("verified-on cannot be in the future")
    return verified.isoformat()


def validation_is_complete(validation: dict[str, object]) -> bool:
    return bool(
        validation.get("aggregate") == "pass"
        and validation.get("technical") == "pass"
        and validation.get("visual") == "pass"
        and validation.get("deliverable_ready") is True
    )


def export_validation_status(
    source_validation: dict[str, object],
    track_validation: dict[str, object] | None,
    track_required: bool = False,
) -> tuple[str, bool]:
    track_complete = (
        track_validation is not None and validation_is_complete(track_validation)
        if track_required
        else True
    )
    source_validation_complete = (
        validation_is_complete(source_validation) and track_complete
    )
    return (
        ("pending_visual_validation", True)
        if source_validation_complete
        else ("diagnostic_unvalidated", False)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--platform", type=parse_platform, required=True)
    parser.add_argument("--size", type=parse_size, required=True)
    parser.add_argument("--max-bytes", type=int)
    parser.add_argument(
        "--frame-track",
        choices=("keyframes", "render"),
        default="keyframes",
        help="keyframes preserves authored frames; render uses motion.render metadata",
    )
    parser.add_argument(
        "--track-report",
        type=Path,
        help=(
            "required pass report for a render track unless --allow-unvalidated "
            "is diagnostic"
        ),
    )
    parser.add_argument(
        "--fps-candidates",
        type=parse_fps_candidates,
        help="render-track fallback order such as 30,24,20,15",
    )
    parser.add_argument(
        "--min-colors",
        type=int,
        default=32,
        help="minimum shared-palette size allowed during byte-limit search",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preview-output", type=Path)
    parser.add_argument("--preview-max-bytes", type=int)
    parser.add_argument("--preview-frame", default="auto", help="'auto' or a 1-based frame number")
    parser.add_argument("--report-output", type=Path)
    parser.add_argument("--alpha-threshold", type=int, default=96, choices=range(1, 255))
    parser.add_argument("--spec-url", type=parse_spec_url, required=True)
    parser.add_argument("--verified-on", type=parse_verified_on, required=True)
    parser.add_argument("--allow-unvalidated", action="store_true")
    args = parser.parse_args()
    if args.max_bytes is not None and args.max_bytes <= 0:
        parser.error("--max-bytes must be positive")
    if args.preview_max_bytes is not None and args.preview_max_bytes <= 0:
        parser.error("--preview-max-bytes must be positive")
    if not 1 <= args.min_colors <= 255:
        parser.error("--min-colors must be between 1 and 255")
    if args.fps_candidates and args.frame_track != "render":
        parser.error("--fps-candidates requires --frame-track render")
    if args.track_report and args.frame_track != "render":
        parser.error("--track-report requires --frame-track render")
    package = args.package.resolve()
    if args.track_report and not args.track_report.resolve().is_relative_to(package):
        parser.error("--track-report must stay beneath the package directory")

    try:
        export_dir = prepare_export_directory(package, args.platform)
        output = direct_export_path(export_dir, args.output, "sticker.gif", "--output")
        preview_output = (
            direct_export_path(
                export_dir,
                args.preview_output,
                "preview.png",
                "--preview-output",
            )
            if args.preview_output is not None
            else None
        )
        report_path = direct_export_path(
            export_dir,
            args.report_output,
            f"{output.stem}.export-report.json",
            "--report-output",
        )
    except ValueError as exc:
        parser.error(str(exc))
    if output.suffix.lower() != ".gif":
        parser.error("--output must end in .gif")
    if preview_output is not None and preview_output.suffix.lower() != ".png":
        parser.error("--preview-output must end in .png")
    if report_path.suffix.lower() != ".json":
        parser.error("--report-output must end in .json")
    final_paths = [output, report_path]
    if preview_output is not None:
        final_paths.append(preview_output)
    if len({path.resolve() for path in final_paths}) != len(final_paths):
        parser.error("GIF, preview, and report outputs must use distinct paths")
    try:
        previous_artifacts = previous_export_artifacts(
            output,
            preview_output,
            report_path,
            export_dir,
        )
    except ValueError as exc:
        parser.error(str(exc))

    frames, durations, motion, source_validation, track_validation = (
        load_validated_package(
            package,
            args.allow_unvalidated,
            args.frame_track,
            args.track_report,
        )
    )
    source_report_path = package / "validation" / "report.json"
    source_report = json.loads(source_report_path.read_text(encoding="utf-8"))
    source_artifact_fingerprint = source_report.get("artifact_fingerprint")
    if not isinstance(source_artifact_fingerprint, str):
        raise ValueError("package validation report has no artifact fingerprint")
    loop = motion.get("loop", True)
    if not isinstance(loop, bool):
        raise ValueError("motion.loop must be a boolean")
    resampling = motion.get("resampling", "lanczos")
    if resampling not in RESAMPLING_FILTERS:
        raise ValueError("motion.resampling must be 'lanczos' or 'nearest'")
    resized = [fit_frame(frame, args.size, str(resampling)) for frame in frames]
    with tempfile.TemporaryDirectory(prefix=".export-staging-", dir=export_dir) as temporary:
        staging = Path(temporary)
        staged_output = staging / output.name
        (
            exported_frames,
            exported_durations,
            colors,
            gif_bytes,
            selected_fps,
            export_attempts,
        ) = export_gif(
            resized,
            durations,
            staged_output,
            args.max_bytes,
            args.alpha_threshold,
            loop,
            args.min_colors,
            args.fps_candidates,
        )
        validation = validate_gif(
            staged_output,
            args.size,
            len(exported_frames),
            exported_durations,
            loop,
            allow_frame_collapse=args.fps_candidates is not None,
        )

        preview_record = None
        staged_preview = None
        if preview_output is not None:
            if args.preview_frame == "auto":
                preview_frame, preview_index = automatic_preview_frame(
                    package,
                    motion,
                    args.size,
                    str(resampling),
                )
                preview_frame_source = "authored"
            else:
                try:
                    preview_index = int(args.preview_frame) - 1
                except ValueError as exc:
                    raise ValueError(
                        "--preview-frame must be 'auto' or a 1-based frame number"
                    ) from exc
                if not 0 <= preview_index < len(exported_frames):
                    raise ValueError("--preview-frame is outside the exported frame range")
                preview_frame = exported_frames[preview_index]
                preview_frame_source = "exported"
            staged_preview = staging / preview_output.name
            mode, preview_bytes, preview_colors = write_preview(
                preview_frame,
                staged_preview,
                args.preview_max_bytes,
            )
            preview_record = {
                "path": preview_output.name,
                "frame": preview_index + 1,
                "frame_source": preview_frame_source,
                "mode": mode,
                "colors": preview_colors,
                "bytes": preview_bytes,
                "max_bytes": args.preview_max_bytes,
                "sha256": sha256_path(staged_preview),
            }

        report_status, source_validation_complete = export_validation_status(
            source_validation,
            track_validation,
            track_required=args.frame_track == "render",
        )
        validation_artifact_entries = [(output.name, staged_output)]
        if staged_preview is not None and preview_output is not None:
            validation_artifact_entries.append((preview_output.name, staged_preview))
        artifact_fingerprint = fingerprint_files(
            [
                (f"artifact:{name}", path)
                for name, path in validation_artifact_entries
            ]
        )
        validation_artifacts = [
            {"path": name, "sha256": sha256_path(path)}
            for name, path in validation_artifact_entries
        ]
        report = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "status": report_status,
            "source_validation_complete": source_validation_complete,
            "deliverable_ready": False,
            "artifact_scope": "export_files",
            "policy_overrides": [],
            "artifact_fingerprint": artifact_fingerprint,
            "validation_artifacts": validation_artifacts,
            "technical_validation": {
                "status": "pass",
                "checks": validation["checks"],
            },
            "visual_validation": {
                "status": "pending",
                "required": ["identity", "meaning", "loop", "alpha", "small_size"],
                "notes": {},
            },
            "platform": args.platform,
            "verified_on": args.verified_on,
            "spec_url": args.spec_url,
            "source_package": "../..",
            "source_validation": source_validation,
            "source_validation_report": {
                "path": "../../validation/report.json",
                "sha256": sha256_path(source_report_path),
                "artifact_fingerprint": source_artifact_fingerprint,
            },
            "frame_track": args.frame_track,
            "track_validation": track_validation,
            "track_report": (
                {
                    "path": str(args.track_report.resolve().relative_to(package)),
                    "sha256": sha256_path(args.track_report),
                }
                if args.track_report is not None
                else None
            ),
            "canvas": list(args.size),
            "resampling": resampling,
            "source_frame_count": len(resized),
            "source_total_duration_ms": sum(durations),
            "frame_count": len(exported_frames),
            "total_duration_ms": sum(exported_durations),
            "gif": {
                "path": output.name,
                "bytes": gif_bytes,
                "max_bytes": args.max_bytes,
                "colors": colors,
                "selected_fps": selected_fps,
                "min_colors": args.min_colors,
                "attempts": export_attempts,
                "alpha_threshold": args.alpha_threshold,
                "sha256": sha256_path(staged_output),
                "validation": validation,
            },
            "preview": preview_record,
        }
        validate_report_contract(report)
        validate_report_state(report)
        staged_report = staging / report_path.name
        staged_report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        staged_entries = [(staged_output, output)]
        if staged_preview is not None and preview_output is not None:
            staged_entries.append((staged_preview, preview_output))
        staged_entries.append((staged_report, report_path))
        new_artifacts = {
            final.resolve()
            for _, final in staged_entries
        }
        removals = tuple(
            path
            for path in previous_artifacts
            if path.resolve() not in new_artifacts
        )
        commit_staged_files(staged_entries, staging, removals)
    print(f"Wrote {output} ({gif_bytes} bytes, {colors} colors)")
    if preview_record:
        print(f"Wrote {preview_output} ({preview_record['bytes']} bytes)")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
