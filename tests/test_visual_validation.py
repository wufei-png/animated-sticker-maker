from __future__ import annotations

import argparse
import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from support import (
    atomic_io,
    artifact_integrity,
    export_platform_gif,
    frame_metrics,
    make_frame,
    media_validation,
    packaged_motion,
    passing_export_checks,
    passing_package_checks,
    record_visual_validation,
    reference_metadata,
    validation_integrity,
    write_sticker_webp,
)


class RecordVisualValidationTests(unittest.TestCase):
    def make_report(self, root: Path, source_validation_complete: bool = True) -> Path:
        package = root / "package"
        frames_dir = package / "source" / "frames"
        validation_dir = package / "validation"
        export_dir = package / "exports" / "test-platform"
        frames_dir.mkdir(parents=True, exist_ok=True)
        validation_dir.mkdir(parents=True, exist_ok=True)
        export_dir.mkdir(parents=True, exist_ok=True)
        make_frame(frames_dir / "000.png", (20, 80, 70, 255))
        make_frame(frames_dir / "001.png", (80, 140, 130, 255))
        reference = reference_metadata()
        (package / "source" / "reference.json").write_text(
            json.dumps(reference),
            encoding="utf-8",
        )
        (package / "source" / "motion.json").write_text(
            json.dumps(
                packaged_motion(
                    [
                        {"file": "frames/000.png", "duration_ms": 600},
                        {"file": "frames/001.png", "duration_ms": 600},
                    ]
                )
            ),
            encoding="utf-8",
        )
        alpha_guard_applied = write_sticker_webp(
            package / "sticker.webp",
            [frames_dir / "000.png", frames_dir / "001.png"],
            [600, 600],
        )
        source_fingerprint = artifact_integrity.package_fingerprint(package)
        source_report_path = validation_dir / "report.json"
        source_snapshot = {
            "aggregate": (
                "pass" if source_validation_complete else "pending_visual_validation"
            ),
            "technical": "pass",
            "visual": "pass" if source_validation_complete else "pending",
            "deliverable_ready": source_validation_complete,
        }
        source_visual: dict[str, object] = {
            "status": "pass" if source_validation_complete else "pending",
            "required": list(validation_integrity.NOTE_FIELDS),
            "notes": {},
        }
        if source_validation_complete:
            source_visual["notes"] = {
                "identity": "stable",
                "meaning": "clear",
                "loop": "clean",
                "alpha": "clean",
                "small_size": "readable",
            }
        source_report_path.write_text(
            json.dumps(
                {
                    "schema_version": validation_integrity.REPORT_SCHEMA_VERSION,
                    "status": source_snapshot["aggregate"],
                    "deliverable_ready": source_validation_complete,
                    "artifact_scope": "package_source",
                    "policy_overrides": [
                        {
                            "check_id": "frame_count_in_default_range",
                            "source": "--allow-nonstandard-frame-count",
                            "actual": 2,
                            "default_range": [4, 8],
                        }
                    ],
                    "artifact_fingerprint": source_fingerprint,
                    "canvas": [16, 16],
                    "frame_count": 2,
                    "total_duration_ms": 1200,
                    "resampling": "lanczos",
                    "webp_encoding": {
                        "lossless": False,
                        "alpha_guard_applied": alpha_guard_applied,
                    },
                    "reference": reference,
                    "render_track": None,
                    "frames": frame_metrics(
                        [frames_dir / "000.png", frames_dir / "001.png"]
                    ),
                    "technical_validation": {
                        "status": "pass",
                        "checks": {
                            **passing_package_checks(),
                            "frame_count_in_default_range": False,
                        },
                    },
                    "visual_validation": source_visual,
                }
            ),
            encoding="utf-8",
        )
        artifact = export_dir / "sticker.gif"
        export_frames = []
        for frame_path in (frames_dir / "000.png", frames_dir / "001.png"):
            with Image.open(frame_path) as image:
                export_frames.append(image.convert("RGBA"))
        export_platform_gif.write_gif(
            export_frames,
            [600, 600],
            artifact,
            32,
            96,
            True,
        )
        gif_validation = media_validation.validate_gif(
            artifact,
            (16, 16),
            2,
            [600, 600],
            True,
        )
        report_path = export_dir / "sticker.export-report.json"
        fingerprint = artifact_integrity.fingerprint_files(
            [("artifact:sticker.gif", artifact)]
        )
        report_path.write_text(
            json.dumps(
                {
                    "schema_version": validation_integrity.REPORT_SCHEMA_VERSION,
                    "status": (
                        "pending_visual_validation"
                        if source_validation_complete
                        else "diagnostic_unvalidated"
                    ),
                    "source_validation_complete": source_validation_complete,
                    "deliverable_ready": False,
                    "artifact_scope": "export_files",
                    "policy_overrides": [],
                    "artifact_fingerprint": fingerprint,
                    "validation_artifacts": [
                        {
                            "path": "sticker.gif",
                            "sha256": artifact_integrity.sha256_path(artifact),
                        }
                    ],
                    "gif": {
                        "path": "sticker.gif",
                        "bytes": artifact.stat().st_size,
                        "max_bytes": None,
                        "colors": 32,
                        "selected_fps": None,
                        "min_colors": 32,
                        "attempts": [
                            {
                                "fps": None,
                                "colors": 32,
                                "bytes": artifact.stat().st_size,
                            }
                        ],
                        "alpha_threshold": 96,
                        "sha256": artifact_integrity.sha256_path(artifact),
                        "validation": gif_validation,
                    },
                    "preview": None,
                    "technical_validation": {
                        "status": "pass",
                        "checks": passing_export_checks(),
                    },
                    "visual_validation": {
                        "status": "pending",
                        "required": list(validation_integrity.NOTE_FIELDS),
                        "notes": {},
                    },
                    "platform": "test-platform",
                    "verified_on": "1990-07-31",
                    "spec_url": "https://www.w3.org/Graphics/GIF/spec-gif89a.txt",
                    "source_package": "../..",
                    "source_validation": source_snapshot,
                    "source_validation_report": {
                        "path": "../../validation/report.json",
                        "sha256": artifact_integrity.sha256_path(source_report_path),
                        "artifact_fingerprint": source_fingerprint,
                    },
                    "frame_track": "keyframes",
                    "track_validation": None,
                    "track_report": None,
                    "canvas": [16, 16],
                    "resampling": "lanczos",
                    "source_frame_count": 2,
                    "source_total_duration_ms": 1200,
                    "frame_count": 2,
                    "total_duration_ms": 1200,
                }
            ),
            encoding="utf-8",
        )
        return report_path

    def validation_args(self, report: Path, **overrides: object) -> argparse.Namespace:
        values = {
            "report": report,
            "status": "pass",
            "identity": "stable",
            "meaning": "clear",
            "loop": "clean",
            "alpha": "clean",
            "small_size": "readable",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_validation_pass_is_bound_to_unchanged_export_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            record_visual_validation.update_report(self.validation_args(report_path))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "pass")
            self.assertTrue(report["deliverable_ready"])

    def test_atomic_validation_update_preserves_report_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            report_path.chmod(0o640)

            original_open = atomic_io.os.open
            with mock.patch.object(
                atomic_io.os,
                "open",
                wraps=original_open,
            ) as open_file:
                record_visual_validation.update_report(
                    self.validation_args(report_path)
                )

            self.assertEqual(
                stat.S_IMODE(report_path.stat().st_mode),
                0o640,
            )
            self.assertEqual(open_file.call_args.args[2], 0o640)

    def test_validation_rejects_changed_export_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            (report_path.parent / "sticker.gif").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "artifacts changed"):
                record_visual_validation.update_report(
                    self.validation_args(report_path)
                )

    def test_validation_rejects_incorrect_declared_artifact_sha(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["validation_artifacts"][0]["sha256"] = "0" * 64
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sha256 does not match"):
                record_visual_validation.update_report(
                    self.validation_args(report_path)
                )

    def test_validation_requires_exact_export_artifact_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["gif"]["path"] = "unbound.gif"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must exactly match"):
                record_visual_validation.update_report(
                    self.validation_args(report_path)
                )

    def test_validation_rejects_placeholder_technical_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["technical_validation"]["checks"] = {"placeholder": True}
            report_path.write_text(json.dumps(report), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "evidence contract"):
                record_visual_validation.update_report(
                    self.validation_args(report_path)
                )

    def test_validation_recomputes_package_frame_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            source_report_path = (
                report_path.parent.parent.parent / "validation" / "report.json"
            )
            source_report = json.loads(
                source_report_path.read_text(encoding="utf-8")
            )
            source_report["frames"][0]["border_is_transparent"] = False

            with self.assertRaisesRegex(
                ValueError,
                "package report frames do not match current packaged frames",
            ):
                validation_integrity.validate_report_binding(
                    source_report_path,
                    source_report,
                )

    def test_validation_recomputes_gif_after_hash_rebinding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            gif = report_path.parent / report["gif"]["path"]
            gif.write_bytes(b"not-a-gif")
            digest = artifact_integrity.sha256_path(gif)
            report["gif"]["bytes"] = gif.stat().st_size
            report["gif"]["attempts"][-1]["bytes"] = gif.stat().st_size
            report["gif"]["sha256"] = digest
            report["validation_artifacts"][0]["sha256"] = digest
            report["artifact_fingerprint"] = (
                artifact_integrity.report_artifact_fingerprint(
                    report_path,
                    report,
                )
            )

            with self.assertRaisesRegex(
                ValueError,
                "current GIF media failed validation",
            ):
                validation_integrity.validate_report_binding(
                    report_path,
                    report,
                )

    def test_validation_recomputes_preview_media(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            preview = report_path.parent / "preview.png"
            Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(preview)
            preview_digest = artifact_integrity.sha256_path(preview)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["preview"] = {
                "path": preview.name,
                "frame": 1,
                "frame_source": "authored",
                "mode": "rgba",
                "colors": None,
                "bytes": preview.stat().st_size,
                "max_bytes": None,
                "sha256": preview_digest,
            }
            report["validation_artifacts"].append(
                {"path": preview.name, "sha256": preview_digest}
            )
            report["artifact_fingerprint"] = (
                artifact_integrity.report_artifact_fingerprint(
                    report_path,
                    report,
                )
            )

            with self.assertRaisesRegex(
                ValueError,
                "preview border must be transparent",
            ):
                validation_integrity.validate_report_binding(
                    report_path,
                    report,
                )

    def test_validation_rejects_open_nested_records(self) -> None:
        mutations = {
            "gif-colors-type": (
                lambda report: report["gif"].__setitem__("colors", "32"),
                "gif.colors must be a supported palette size",
            ),
            "gif-validation-extra": (
                lambda report: report["gif"]["validation"].__setitem__(
                    "comment",
                    "unbound",
                ),
                "gif.validation must contain exactly",
            ),
        }
        for name, (mutate, error) in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                report_path = self.make_report(Path(temporary))
                report = json.loads(report_path.read_text(encoding="utf-8"))
                mutate(report)
                with self.assertRaisesRegex(ValueError, error):
                    validation_integrity.validate_report_binding(
                        report_path,
                        report,
                    )

        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            record_visual_validation.update_report(
                self.validation_args(report_path)
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["visual_validation"]["notes"]["comment"] = "unbound"
            with self.assertRaisesRegex(
                ValueError,
                "visual_validation.notes must contain exactly",
            ):
                validation_integrity.validate_report_binding(
                    report_path,
                    report,
                )

    def test_validation_rejects_invalid_export_provenance_and_limits(self) -> None:
        cases = {
            "missing-spec": (
                lambda report: report.pop("spec_url"),
                "spec_url",
            ),
            "future-verification": (
                lambda report: report.__setitem__("verified_on", "2999-01-01"),
                "cannot be in the future",
            ),
            "wrong-resampling": (
                lambda report: report.__setitem__("resampling", "nearest"),
                "resampling must match",
            ),
            "gif-over-limit": (
                lambda report: report["gif"].__setitem__("max_bytes", 1),
                "exceeds gif.max_bytes",
            ),
            "gif-low-bytes": (
                lambda report: (
                    report["gif"].__setitem__("bytes", 1),
                    report["gif"]["attempts"][-1].__setitem__("bytes", 1),
                ),
                "gif.bytes does not match",
            ),
            "gif-wrong-sha": (
                lambda report: report["gif"].__setitem__("sha256", "0" * 64),
                "gif.sha256 does not match",
            ),
        }
        for name, (mutate, error) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                report_path = self.make_report(Path(temporary))
                report = json.loads(report_path.read_text(encoding="utf-8"))
                mutate(report)
                report_path.write_text(json.dumps(report), encoding="utf-8")

                with self.assertRaisesRegex(ValueError, error):
                    record_visual_validation.update_report(
                        self.validation_args(report_path)
                    )

    def test_validation_binds_preview_metadata_to_its_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            preview = report_path.parent / "preview.png"
            with Image.open(
                report_path.parent.parent.parent / "source" / "frames" / "000.png"
            ) as image:
                image.save(preview, format="PNG")
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["validation_artifacts"].append(
                {
                    "path": preview.name,
                    "sha256": artifact_integrity.sha256_path(preview),
                }
            )
            report["artifact_fingerprint"] = artifact_integrity.fingerprint_files(
                [
                    ("artifact:sticker.gif", report_path.parent / "sticker.gif"),
                    ("artifact:preview.png", preview),
                ]
            )
            report["preview"] = {
                "path": preview.name,
                "frame": 1,
                "frame_source": "authored",
                "mode": "rgba",
                "colors": None,
                "bytes": preview.stat().st_size - 1,
                "max_bytes": None,
                "sha256": artifact_integrity.sha256_path(preview),
            }
            report_path.write_text(json.dumps(report), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "preview.bytes does not match"):
                record_visual_validation.update_report(
                    self.validation_args(report_path)
                )

    def test_validation_rejects_changed_source_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            source_report_path = (
                report_path.parent.parent.parent / "validation" / "report.json"
            )
            source_report = json.loads(source_report_path.read_text(encoding="utf-8"))
            source_report["comment"] = "changed after export"
            source_report_path.write_text(json.dumps(source_report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source validation report changed"):
                record_visual_validation.update_report(
                    self.validation_args(report_path)
                )

    def test_validation_rejects_invalid_or_contradictory_frame_track(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["frame_track"] = "other"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "frame_track must be"):
                record_visual_validation.update_report(
                    self.validation_args(report_path)
                )

            report_path = self.make_report(Path(temporary))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["track_validation"] = dict(report["source_validation"])
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must not declare"):
                record_visual_validation.update_report(
                    self.validation_args(report_path)
                )

    def test_empty_notes_and_unvalidated_source_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report_path = self.make_report(root)
            with self.assertRaisesRegex(ValueError, "notes must be non-empty"):
                record_visual_validation.update_report(
                    self.validation_args(report_path, alpha="   ")
                )
            diagnostic = self.make_report(root, source_validation_complete=False)
            with self.assertRaisesRegex(ValueError, "cannot become deliverable"):
                record_visual_validation.update_report(
                    self.validation_args(diagnostic)
                )


if __name__ == "__main__":
    unittest.main()
