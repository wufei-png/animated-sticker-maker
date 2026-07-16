#!/usr/bin/env python3
"""Build the data model and HTML for one exact visual-validation boundary."""

from __future__ import annotations

import base64
import json
import os
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from PIL import Image

from artifact_integrity import safe_relative_file, sha256_path
from media_validation import webp_animation_durations
from motion_schema import validate_motion
from review_i18n import language_text
from review_template import render_review_html
from validation_integrity import validate_report_binding, validate_report_state


SUPPORTED_SCOPES = {"package_source", "render_track", "export_files"}
REVIEW_FIELDS = ("identity", "meaning", "loop", "alpha", "small_size")
OVERVIEW_LIMIT = 24


def load_json_object(path: Path, label: str) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def resolve_output_path(report_path: Path, requested: Path | None) -> Path:
    report_dir = report_path.parent.resolve()
    if requested is None:
        output = report_dir / f"{report_path.stem}.review.html"
    elif requested.is_absolute():
        output = requested.resolve()
    elif len(requested.parts) == 1:
        output = report_dir / requested
    else:
        raise ValueError("--output must be a direct child of the report directory")
    if output.parent.resolve() != report_dir:
        raise ValueError("--output must stay in the report directory")
    if output.suffix.lower() != ".html":
        raise ValueError("--output must end in .html")
    if output.exists() and not output.is_file():
        raise ValueError(f"--output must not replace a directory: {output}")
    return output


def package_for_report(
    report_path: Path,
    report: dict[str, object],
) -> Path:
    scope = report.get("artifact_scope")
    if scope in {"package_source", "render_track"}:
        return report_path.parent.parent.resolve()
    if scope == "export_files":
        return report_path.parent.parent.parent.resolve()
    raise ValueError(f"unsupported report artifact_scope: {scope!r}")


def validate_boundary(
    report_path: Path,
) -> tuple[dict[str, object], dict[str, object], Path, Path]:
    report_path = report_path.resolve()
    if not report_path.is_file():
        raise FileNotFoundError(f"validation report not found: {report_path}")
    report = load_json_object(report_path, "validation report")
    scope = report.get("artifact_scope")
    if scope not in SUPPORTED_SCOPES:
        raise ValueError(
            "review report artifact_scope must be package_source, "
            "render_track, or export_files"
        )
    validate_report_state(report)
    validate_report_binding(report_path, report)
    package = package_for_report(report_path, report)
    expected_report = {
        "package_source": package / "validation" / "report.json",
        "render_track": package / "validation" / "render-report.json",
    }.get(str(scope))
    if expected_report is not None and report_path != expected_report.resolve():
        raise ValueError(
            f"{scope} review must use the canonical report: {expected_report}"
        )

    motion_path = package / "source" / "motion.json"
    motion = validate_motion(
        load_json_object(motion_path, "packaged motion"),
        packaged=True,
    )
    source_report_path = package / "validation" / "report.json"
    source_report = load_json_object(
        source_report_path,
        "package source validation report",
    )
    validate_report_state(source_report)
    validate_report_binding(source_report_path, source_report)
    return report, motion, package, source_report_path


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


def resolve_reference(
    package: Path,
    source_report: dict[str, object],
    motion: dict[str, object],
    output_dir: Path,
    reference_image: Path | None,
    text: dict[str, object],
) -> dict[str, object]:
    source = package / "source"
    metadata_path = source / "reference.json"
    metadata = load_json_object(metadata_path, "reference metadata")
    if source_report.get("reference") != metadata:
        raise ValueError(
            "package source report reference metadata is inconsistent"
        )
    motion_reference = motion.get("reference")
    if not isinstance(motion_reference, dict) or any(
        metadata.get(field) != motion_reference.get(field)
        for field in ("filename", "sha256", "included_path")
    ):
        raise ValueError(
            "packaged motion reference metadata is inconsistent"
        )
    expected_sha = metadata.get("sha256")
    if not isinstance(expected_sha, str):
        raise ValueError("reference metadata must contain sha256")

    included_path = metadata.get("included_path")
    if included_path is not None:
        if reference_image is not None:
            raise ValueError(
                "--reference-image must be omitted when the package includes "
                "its bound reference"
            )
        path = safe_relative_file(
            source,
            included_path,
            "reference.included_path",
        )
        if sha256_path(path) != expected_sha:
            raise ValueError("included reference does not match its SHA-256")
        with Image.open(path) as image:
            image.load()
        src = relative_media_url(path, output_dir)
        reference_labels = text["reference_labels"]
        assert isinstance(reference_labels, dict)
        source_kind = reference_labels["included"]
    else:
        if reference_image is None:
            raise ValueError(
                "--reference-image is required because the package does not "
                "include its bound reference"
            )
        path = reference_image.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"reference image not found: {path}")
        if sha256_path(path) != expected_sha:
            raise ValueError(
                "--reference-image does not match the package reference SHA-256"
            )
        src = image_data_uri(path)
        reference_labels = text["reference_labels"]
        assert isinstance(reference_labels, dict)
        source_kind = reference_labels["external"]

    return {
        "src": src,
        "label": source_kind,
        "filename": metadata.get("filename"),
        "sha256": expected_sha,
        "size": metadata.get("size"),
        "mode": metadata.get("mode"),
        "format": metadata.get("format"),
    }


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
            display_path = str(path.resolve())
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


def overview_indices(
    frame_count: int,
    limit: int = OVERVIEW_LIMIT,
    *,
    required_index: int | None = None,
) -> list[int]:
    if frame_count <= limit:
        return list(range(frame_count))
    indices = sorted(
        {
            round(index * (frame_count - 1) / (limit - 1))
            for index in range(limit)
        }
    )
    if (
        required_index is not None
        and 0 <= required_index < frame_count
        and required_index not in indices
    ):
        replace_at = min(
            range(1, len(indices) - 1),
            key=lambda index: abs(indices[index] - required_index),
        )
        indices[replace_at] = required_index
        indices = sorted(set(indices))
    return indices


def semantic_hold(
    motion: dict[str, object],
) -> dict[str, object]:
    entries = motion["frames"]
    assert isinstance(entries, list)
    semantic_path = motion.get("semantic_hold_frame")
    index = None
    if isinstance(semantic_path, str):
        for candidate_index, entry in enumerate(entries):
            if isinstance(entry, dict) and entry.get("file") == semantic_path:
                index = candidate_index
                break
    declared = index is not None
    if index is None:
        index = max(
            range(len(entries)),
            key=lambda candidate: int(entries[candidate]["duration_ms"]),
        )
    start_ms = sum(
        int(entry["duration_ms"]) for entry in entries[:index]
    )
    duration_ms = int(entries[index]["duration_ms"])
    return {
        "authored_index": index,
        "start_ms": start_ms,
        "duration_ms": duration_ms,
        "midpoint_ms": start_ms + duration_ms / 2,
        "declared": declared,
        "description": entries[index].get("description"),
    }


def sequence_frame_at_time(
    frames: list[dict[str, object]],
    target_ms: float,
) -> int:
    elapsed = 0
    for index, frame in enumerate(frames):
        elapsed += int(frame["duration_ms"])
        if target_ms < elapsed:
            return index
    return len(frames) - 1


def primary_file_record(
    role: str,
    path: Path,
    package: Path,
) -> dict[str, object]:
    try:
        display = path.resolve().relative_to(package.resolve()).as_posix()
    except ValueError:
        display = str(path.resolve())
    return {
        "role": role,
        "path": display,
        "sha256": sha256_path(path),
    }


def build_technical_details(
    report_path: Path,
    report: dict[str, object],
    motion: dict[str, object],
    package: Path,
    main_path: Path | None,
    preview_path: Path | None,
    reference: dict[str, object],
    text: dict[str, object],
) -> dict[str, object]:
    technical = report["technical_validation"]
    assert isinstance(technical, dict)
    checks = technical["checks"]
    assert isinstance(checks, dict)
    visual = report["visual_validation"]
    assert isinstance(visual, dict)
    canvas = report.get("canvas")
    if not isinstance(canvas, list):
        canvas = motion["canvas"]
    labels = text["technical_labels"]
    file_roles = text["file_roles"]
    status_labels = text["status_labels"]
    boolean_labels = text["boolean_labels"]
    assert isinstance(labels, dict)
    assert isinstance(file_roles, dict)
    assert isinstance(status_labels, dict)
    assert isinstance(boolean_labels, dict)

    def display_status(value: object) -> object:
        return status_labels.get(value, value)

    summary: list[dict[str, object]] = [
        {"label": labels["artifact_scope"], "value": report["artifact_scope"]},
        {
            "label": labels["aggregate_status"],
            "value": display_status(report["status"]),
        },
        {
            "label": labels["technical"],
            "value": display_status(technical["status"]),
        },
        {
            "label": labels["visual"],
            "value": display_status(visual["status"]),
        },
        {
            "label": labels["deliverable_ready"],
            "value": boolean_labels[
                str(report.get("deliverable_ready") is True).lower()
            ],
        },
        {
            "label": labels["canvas"],
            "value": " × ".join(str(value) for value in canvas),
        },
        {"label": labels["frame_count"], "value": report.get("frame_count")},
        {
            "label": labels["total_duration"],
            "value": (
                f"{report.get('total_duration_ms')} ms"
                if report.get("total_duration_ms") is not None
                else None
            ),
        },
        {
            "label": labels["loop"],
            "value": boolean_labels[str(motion["loop"]).lower()],
        },
        {"label": labels["resampling"], "value": motion["resampling"]},
    ]
    if report.get("artifact_scope") == "render_track":
        summary.append(
            {"label": labels["target_fps"], "value": report.get("target_fps")}
        )
    if report.get("artifact_scope") == "export_files":
        gif = report.get("gif")
        assert isinstance(gif, dict)
        summary.extend(
            [
                {"label": labels["platform"], "value": report.get("platform")},
                {
                    "label": labels["frame_track"],
                    "value": report.get("frame_track"),
                },
                {"label": labels["gif_bytes"], "value": gif.get("bytes")},
                {
                    "label": labels["gif_max_bytes"],
                    "value": gif.get("max_bytes"),
                },
                {
                    "label": labels["palette_colors"],
                    "value": gif.get("colors"),
                },
                {
                    "label": labels["selected_fps"],
                    "value": gif.get("selected_fps"),
                },
                {
                    "label": labels["verified_on"],
                    "value": report.get("verified_on"),
                },
            ]
        )
    summary = [item for item in summary if item["value"] not in {None, ""}]

    files = [
        primary_file_record(
            str(file_roles["validation_report"]),
            report_path,
            package,
        ),
        primary_file_record(
            str(file_roles["packaged_motion"]),
            package / "source" / "motion.json",
            package,
        ),
    ]
    if main_path is not None and main_path.is_file():
        files.append(
            primary_file_record(
                str(file_roles["primary_media"]),
                main_path,
                package,
            )
        )
    if preview_path is not None:
        files.append(
            primary_file_record(
                str(file_roles["platform_preview"]),
                preview_path,
                package,
            )
        )
    files.append(
        {
            "role": file_roles["reference_image"],
            "path": str(reference.get("filename")),
            "sha256": reference.get("sha256"),
        }
    )

    return {
        "summary": summary,
        "checks": [
            {"id": check_id, "passed": passed}
            for check_id, passed in checks.items()
        ],
        "files": files,
        "spec_url": report.get("spec_url"),
    }


def build_review_model(
    report_path: Path,
    *,
    reference_image: Path | None,
    output_path: Path,
    language: str = "en",
) -> dict[str, object]:
    text = language_text(language)
    report, motion, package, source_report_path = validate_boundary(report_path)
    scope = str(report["artifact_scope"])
    output_dir = output_path.parent
    source = package / "source"
    source_report = load_json_object(
        source_report_path,
        "package source validation report",
    )
    reference = resolve_reference(
        package,
        source_report,
        motion,
        output_dir,
        reference_image,
        text,
    )
    authored = frame_records(
        motion["frames"],
        source,
        output_dir,
        prefix="authored",
    )
    render = motion.get("render")
    rendered = (
        frame_records(
            render["frames"],
            source,
            output_dir,
            prefix="render",
        )
        if isinstance(render, dict)
        else []
    )
    hold = semantic_hold(motion)
    technical = report["technical_validation"]
    assert isinstance(technical, dict)
    technical_pass = technical.get("status") == "pass"
    hero_text = text["hero"]
    formats = text["formats"]
    assert isinstance(hero_text, dict)
    assert isinstance(formats, dict)

    main_path: Path | None = None
    preview_path: Path | None = None
    hero: dict[str, object]
    inspector = authored
    inspector_kind = "authored"
    auxiliary = []
    if scope == "package_source":
        candidate = package / "sticker.webp"
        if candidate.is_file():
            main_path = candidate
            inspector = encoded_frame_records(
                candidate,
                package,
                format_label=str(formats["webp"]),
                description_template=str(
                    text["decoded_frame_description"]
                ),
            )
            inspector_kind = "encoded"
            auxiliary = authored
            hero = {
                "mode": "sequence",
                "title": hero_text["package_title"],
                "subtitle": hero_text["package_subtitle"],
                "format": formats["webp"],
            }
        elif technical_pass:
            raise FileNotFoundError(f"validated sticker.webp is missing: {candidate}")
        else:
            hero = {
                "mode": "missing",
                "title": hero_text["package_missing_title"],
                "subtitle": hero_text["package_missing_subtitle"],
            }
    elif scope == "render_track":
        if not rendered:
            raise ValueError("render_track report requires motion.render.frames")
        inspector = rendered
        inspector_kind = "render"
        auxiliary = authored
        hero = {
            "mode": "sequence",
            "title": hero_text["render_title"],
            "subtitle": hero_text["render_subtitle"],
            "format": formats["render"],
        }
    else:
        gif = report.get("gif")
        if not isinstance(gif, dict):
            raise ValueError("export review requires report.gif")
        main_path = safe_relative_file(
            report_path.parent,
            gif.get("path"),
            "gif.path",
        )
        source_track: list[dict[str, object]]
        frame_track = report.get("frame_track")
        if frame_track == "render":
            if not rendered:
                raise ValueError("render export requires motion.render.frames")
            source_track = rendered
        elif frame_track != "keyframes":
            raise ValueError("export frame_track must be keyframes or render")
        else:
            source_track = authored
        inspector = encoded_frame_records(
            main_path,
            package,
            format_label=str(formats["gif"]),
            description_template=str(text["decoded_frame_description"]),
        )
        inspector_kind = "encoded"
        auxiliary = source_track
        preview = report.get("preview")
        if isinstance(preview, dict):
            preview_path = safe_relative_file(
                report_path.parent,
                preview.get("path"),
                "preview.path",
            )
        hero = {
            "mode": "sequence",
            "title": str(hero_text["export_title"]).format(
                platform=report.get("platform")
            ),
            "subtitle": hero_text["export_subtitle"],
            "format": formats["gif"],
        }

    hold["primary_index"] = sequence_frame_at_time(
        inspector,
        float(hold["midpoint_ms"]),
    )

    visual = report["visual_validation"]
    assert isinstance(visual, dict)
    notes = visual.get("notes")
    if not isinstance(notes, dict):
        notes = {}
    prompt_labels = text["prompt_labels"]
    assert isinstance(prompt_labels, dict)
    review_prompts = [
        {
            "id": field,
            "label": prompt_labels[field],
            "note": notes.get(field),
        }
        for field in REVIEW_FIELDS
    ]

    scope_labels = text["scope_labels"]
    scope_descriptions = text["scope_descriptions"]
    inspector_labels = text["inspector_labels"]
    auxiliary_labels = text["auxiliary_labels"]
    assert isinstance(scope_labels, dict)
    assert isinstance(scope_descriptions, dict)
    assert isinstance(inspector_labels, dict)
    assert isinstance(auxiliary_labels, dict)
    model = {
        "schema_version": 3,
        "language": language,
        "text": text,
        "scope": scope,
        "scope_label": scope_labels[scope],
        "scope_description": scope_descriptions[scope],
        "report_name": report_path.name,
        "report_path": str(report_path.resolve()),
        "report_status": report["status"],
        "technical_status": technical["status"],
        "visual_status": visual["status"],
        "deliverable_ready": report.get("deliverable_ready") is True,
        "artifact_fingerprint": report["artifact_fingerprint"],
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "reference": reference,
        "hero": hero,
        "inspector": {
            "label": inspector_labels[inspector_kind],
            "frames": inspector,
            "overview_indices": overview_indices(
                len(inspector),
                required_index=int(hold["primary_index"]),
            ),
            "total_duration_ms": sum(
                int(frame["duration_ms"]) for frame in inspector
            ),
            "loop": motion["loop"],
        },
        "auxiliary_frames": {
            "label": (
                auxiliary_labels["export"]
                if scope == "export_files"
                else auxiliary_labels["authored"]
            ),
            "frames": auxiliary,
            "overview_indices": overview_indices(len(auxiliary))
            if auxiliary
            else [],
        },
        "semantic_hold": {
            **hold,
        },
        "small_size": {
            "label": text["stress_title"],
        },
        "preview": (
            {
                "src": relative_media_url(preview_path, output_dir),
                "label": formats["preview"],
                "frame": report["preview"].get("frame"),
            }
            if preview_path is not None and isinstance(report.get("preview"), dict)
            else None
        ),
        "review_prompts": review_prompts,
        "technical_details": build_technical_details(
            report_path,
            report,
            motion,
            package,
            main_path,
            preview_path,
            reference,
            text,
        ),
        "resampling": motion["resampling"],
    }
    return model


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(content)
            temporary_path = Path(handle.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def generate_review(
    report: Path,
    *,
    reference_image: Path | None = None,
    output: Path | None = None,
    language: str = "en",
) -> Path:
    report_path = report.resolve()
    output_path = resolve_output_path(report_path, output)
    model = build_review_model(
        report_path,
        reference_image=reference_image,
        output_path=output_path,
        language=language,
    )
    write_atomic(output_path, render_review_html(model))
    return output_path
