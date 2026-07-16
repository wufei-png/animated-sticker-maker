#!/usr/bin/env python3
"""Path containment and transactional replacement for one export set."""

from __future__ import annotations

import json
from pathlib import Path

from artifact_integrity import report_artifact_fingerprint, sha256_path
from validation_integrity import validate_report_state
from validation_schema import validate_report_contract


def prepare_export_directory(package: Path, platform: str) -> Path:
    package = package.resolve()
    exports_root = package / "exports"
    export_dir = exports_root / platform
    for path, parent, label in (
        (exports_root, package, "package exports directory"),
        (export_dir, exports_root, "platform export directory"),
    ):
        if path.is_symlink():
            raise ValueError(f"{label} must not be a symbolic link: {path}")
        if path.exists() and not path.is_dir():
            raise ValueError(f"{label} must be a directory: {path}")
        path.mkdir(parents=True, exist_ok=True)
        if path.resolve().parent != parent.resolve():
            raise ValueError(f"{label} must stay directly beneath {parent}")
    return export_dir


def direct_export_path(
    export_dir: Path,
    requested: Path | None,
    default_name: str,
    label: str,
) -> Path:
    if requested is None:
        path = export_dir / default_name
    elif not requested.is_absolute() and len(requested.parts) == 1:
        path = export_dir / requested
    else:
        path = requested
    if path.resolve().parent != export_dir.resolve():
        raise ValueError(f"{label} must be a direct child of {export_dir}")
    if path.exists() and not path.is_file():
        raise ValueError(f"{label} must not replace a directory: {path}")
    return path


def commit_staged_files(
    entries: list[tuple[Path, Path]],
    staging: Path,
    removals: tuple[Path, ...] = (),
) -> None:
    """Replace one related export set, restoring previous files on error."""
    backups: dict[Path, Path] = {}
    committed: list[Path] = []
    try:
        backup_dir = staging / ".transaction-backups"
        backup_dir.mkdir()
        final_paths = {final.resolve() for _, final in entries}
        if any(path.resolve() in final_paths for path in removals):
            raise ValueError(
                "transaction removals must not overlap replacements"
            )
        affected = [final for _, final in entries] + list(removals)
        for index, final in enumerate(affected):
            if final.exists():
                backup = backup_dir / str(index)
                final.replace(backup)
                backups[final] = backup
        for staged, final in entries:
            staged.replace(final)
            committed.append(final)
    except Exception:
        for final in reversed(committed):
            final.unlink(missing_ok=True)
        for final, backup in backups.items():
            if backup.exists():
                backup.replace(final)
        raise


def previous_export_artifacts(
    output_path: Path,
    preview_path: Path | None,
    report_path: Path,
    export_dir: Path,
) -> set[Path]:
    """Find the one prior set claimed by the target GIF or report path."""
    matching_reports: list[tuple[Path, set[Path]]] = []
    collision_paths = {output_path.resolve(), report_path.resolve()}
    if preview_path is not None:
        collision_paths.add(preview_path.resolve())
    candidates = sorted(
        candidate
        for candidate in export_dir.iterdir()
        if candidate.suffix.lower() == ".json"
    )
    for candidate in candidates:
        is_target_report = candidate == report_path
        if candidate.is_symlink():
            if is_target_report:
                raise ValueError(
                    f"existing report output must not be a symbolic link: {candidate}"
                )
            continue
        if not candidate.is_file():
            continue
        try:
            loaded = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            if is_target_report:
                raise ValueError(
                    f"existing report output is not a readable export report: {candidate}"
                ) from exc
            continue
        gif = loaded.get("gif") if isinstance(loaded, dict) else None
        gif_path = gif.get("path") if isinstance(gif, dict) else None
        preview = loaded.get("preview") if isinstance(loaded, dict) else None
        preview_value = (
            preview.get("path") if isinstance(preview, dict) else None
        )
        preliminary_names = {candidate.name}
        if isinstance(gif_path, str):
            preliminary_names.add(gif_path)
        if isinstance(preview_value, str):
            preliminary_names.add(preview_value)
        if not any(
            path.name in preliminary_names
            for path in (output_path, preview_path, report_path)
            if path is not None
        ):
            continue
        if not isinstance(loaded, dict):
            raise ValueError(
                f"existing report output is not a valid export report: {candidate}"
            )
        try:
            paths = _validated_export_set(candidate, loaded, export_dir)
        except (OSError, ValueError) as exc:
            raise ValueError(
                f"existing export report cannot be transactionally replaced: "
                f"{candidate}: {exc}"
            ) from exc
        overlap = {path.resolve() for path in paths} & collision_paths
        replaces_existing_set = (
            report_path.resolve() in overlap
            or output_path.resolve() in overlap
        )
        if overlap and not replaces_existing_set:
            claimed = ", ".join(sorted(path.name for path in overlap))
            raise ValueError(
                "export output path is already owned by another export report: "
                f"{claimed} ({candidate.name})"
            )
        matching_reports.append((candidate, paths))

    if len(matching_reports) > 1:
        claimed = ", ".join(path.name for path, _ in matching_reports)
        raise ValueError(
            "multiple existing export reports claim the target GIF or report "
            f"output: {claimed}"
        )
    if not matching_reports:
        return set()
    return matching_reports[0][1]


def _validated_export_set(
    report_path: Path,
    report: dict[str, object],
    export_dir: Path,
) -> set[Path]:
    validate_report_contract(report)
    validate_report_state(report)
    if report.get("artifact_scope") != "export_files":
        raise ValueError("artifact_scope must be 'export_files'")

    gif = report.get("gif")
    gif_path = gif.get("path") if isinstance(gif, dict) else None
    if (
        not isinstance(gif_path, str)
        or not gif_path
        or Path(gif_path).suffix.lower() != ".gif"
    ):
        raise ValueError("gif.path must name one GIF file")

    preview = report.get("preview")
    preview_path = None
    if preview is not None:
        preview_path = (
            preview.get("path") if isinstance(preview, dict) else None
        )
        if (
            not isinstance(preview_path, str)
            or not preview_path
            or Path(preview_path).suffix.lower() != ".png"
        ):
            raise ValueError("preview.path must name one PNG file")

    expected_artifacts = [gif_path]
    if preview_path is not None:
        expected_artifacts.append(preview_path)
    if len(set(expected_artifacts)) != len(expected_artifacts):
        raise ValueError("GIF and preview paths must be distinct")

    artifacts = report.get("validation_artifacts")
    artifact_paths = (
        [
            artifact.get("path") if isinstance(artifact, dict) else None
            for artifact in artifacts
        ]
        if isinstance(artifacts, list)
        else None
    )
    if artifact_paths != expected_artifacts:
        raise ValueError(
            "validation_artifacts must exactly match gif.path and preview.path"
        )

    expected_fingerprint = report.get("artifact_fingerprint")
    if (
        not isinstance(expected_fingerprint, str)
        or report_artifact_fingerprint(report_path, report)
        != expected_fingerprint
    ):
        raise ValueError(
            "artifact_fingerprint does not match the declared export files"
        )

    paths = {report_path}
    artifact_records = {
        str(artifact["path"]): artifact
        for artifact in artifacts
        if isinstance(artifact, dict)
    }
    for path_value in expected_artifacts:
        relative = Path(path_value)
        candidate = export_dir / relative
        if (
            relative.is_absolute()
            or len(relative.parts) != 1
            or candidate.resolve().parent != export_dir.resolve()
            or candidate.is_symlink()
        ):
            raise ValueError(
                f"export artifact escapes its directory: {path_value}"
            )
        if candidate.exists() and not candidate.is_file():
            raise ValueError(
                f"export artifact must be a file: {candidate}"
            )
        actual_sha256 = sha256_path(candidate)
        if artifact_records[path_value].get("sha256") != actual_sha256:
            raise ValueError(
                f"validation artifact SHA-256 does not match {path_value}"
            )
        paths.add(candidate)

    gif_record = report["gif"]
    assert isinstance(gif_record, dict)
    gif_file = export_dir / gif_path
    if (
        gif_record.get("sha256") != sha256_path(gif_file)
        or gif_record.get("bytes") != gif_file.stat().st_size
    ):
        raise ValueError("gif metadata does not match its file")
    if preview_path is not None:
        preview_record = report["preview"]
        assert isinstance(preview_record, dict)
        preview_file = export_dir / preview_path
        if (
            preview_record.get("sha256") != sha256_path(preview_file)
            or preview_record.get("bytes") != preview_file.stat().st_size
        ):
            raise ValueError("preview metadata does not match its file")
    return paths
